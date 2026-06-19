"""
url_analyzer.py — Tiflo AI URL / Link Analyzer
==================================================
Fetches URLs, extracts readable content and structured signals, then routes the
result into a higher-quality analysis prompt.
"""

import asyncio
import io
import json
import os
import re
import time
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from groq import Groq
from pypdf import PdfReader

from runtime_state import runtime_metrics

load_dotenv()

_groq = Groq(api_key=os.getenv("GROQ_API_KEY"))
_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,text/plain;q=0.7,*/*;q=0.5",
    "Accept-Language": "en-US,en;q=0.9",
}

NOISE_TAGS = [
    "script",
    "style",
    "nav",
    "header",
    "footer",
    "aside",
    "form",
    "noscript",
    "iframe",
    "svg",
    "canvas",
    "button",
    "input",
    "select",
    "textarea",
]

NOISE_SELECTORS = [
    "[class*='cookie']",
    "[id*='cookie']",
    "[class*='popup']",
    "[id*='popup']",
    "[class*='modal']",
    "[id*='modal']",
    "[class*='banner']",
    "[id*='banner']",
    "[class*='subscribe']",
    "[id*='subscribe']",
    "[aria-label*='cookie']",
    "[data-testid*='cookie']",
]

EXTRACTION_HINTS = [
    "extract",
    "list",
    "price",
    "pricing",
    "spec",
    "specification",
    "email",
    "phone",
    "address",
    "table",
    "data",
    "numbers",
    "metrics",
    "facts",
]


def extract_urls(text: str) -> list[str]:
    pattern = r'https?://[^\s<>"\')\]`]+'
    return list(dict.fromkeys(re.findall(pattern, text or "")))


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _truncate(text: str, limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    output = []
    for item in items:
        clean = _normalize_whitespace(item)
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(clean)
    return output


def _meta_content(soup: BeautifulSoup, *candidates: tuple[str, str]) -> str:
    for attr, value in candidates:
        tag = soup.find("meta", attrs={attr: re.compile(f"^{re.escape(value)}$", re.I)})
        if tag and tag.get("content"):
            return _normalize_whitespace(tag.get("content"))
    return ""


def _extract_table_preview(soup: BeautifulSoup, max_tables: int = 2, max_rows: int = 5) -> str:
    blocks = []
    for table in soup.find_all("table")[:max_tables]:
        rows = []
        for row in table.find_all("tr")[:max_rows]:
            cells = [
                _normalize_whitespace(cell.get_text(" ", strip=True))
                for cell in row.find_all(["th", "td"])
            ]
            cells = [cell for cell in cells if cell]
            if cells:
                rows.append(" | ".join(cells))
        if rows:
            blocks.append("\n".join(rows))
    return "\n\n".join(blocks)


def _extract_key_links(zone: BeautifulSoup, max_links: int = 10) -> list[dict]:
    links = []
    for anchor in zone.find_all("a", href=True):
        text = _normalize_whitespace(anchor.get_text(" ", strip=True))
        href = anchor.get("href", "").strip()
        if not text or not href or href.startswith("#"):
            continue
        links.append({"text": text[:120], "href": href[:400]})
        if len(links) >= max_links:
            break
    return links


def _extract_pdf_text(raw_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(raw_bytes))
    except Exception:
        return ""

    parts = []
    for idx, page in enumerate(reader.pages[:20], start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text.strip():
            parts.append(f"--- PAGE {idx} ---\n{_truncate(text.strip(), 1800)}")
    return "\n\n".join(parts)


def _extract_json_text(raw_bytes: bytes) -> str:
    try:
        payload = json.loads(raw_bytes.decode("utf-8", errors="ignore"))
        pretty = json.dumps(payload, indent=2, ensure_ascii=False)
        return _truncate(pretty, 12000)
    except Exception:
        return _truncate(raw_bytes.decode("utf-8", errors="ignore"), 12000)


def _extract_html_payload(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(NOISE_TAGS):
        tag.decompose()
    for selector in NOISE_SELECTORS:
        for node in soup.select(selector):
            node.decompose()

    title = (
        _meta_content(soup, ("property", "og:title"), ("name", "twitter:title"))
        or _normalize_whitespace((soup.title.get_text(strip=True) if soup.title else ""))
    )
    description = _meta_content(
        soup,
        ("name", "description"),
        ("property", "og:description"),
        ("name", "twitter:description"),
    )
    site_name = _meta_content(soup, ("property", "og:site_name"))

    content_zone = (
        soup.find("article")
        or soup.find("main")
        or soup.find(id=re.compile(r"(content|main|article|post|body)", re.I))
        or soup.find(class_=re.compile(r"(content|article|post|entry|text)", re.I))
        or soup.find("body")
        or soup
    )

    headings = _dedupe([
        heading.get_text(" ", strip=True)
        for heading in content_zone.find_all(["h1", "h2", "h3"])[:20]
    ])[:12]

    text_blocks = []
    for node in content_zone.find_all(["p", "li", "blockquote", "td", "pre", "code"])[:500]:
        text = _normalize_whitespace(node.get_text(" ", strip=True))
        if len(text) >= 25:
            text_blocks.append(text)

    text_blocks = _dedupe(text_blocks)
    content = "\n".join(text_blocks)

    canonical = ""
    canonical_tag = soup.find("link", rel=re.compile("canonical", re.I))
    if canonical_tag and canonical_tag.get("href"):
        canonical = canonical_tag.get("href", "").strip()

    return {
        "title": title,
        "description": _truncate(description, 400),
        "site_name": site_name,
        "canonical_url": canonical,
        "headings": headings,
        "table_preview": _truncate(_extract_table_preview(content_zone), 2500),
        "key_links": _extract_key_links(content_zone),
        "content": _truncate(content, 12000),
        "word_count": len(content.split()),
    }


async def fetch_url_content(url: str, timeout: int = 12) -> dict:
    result = {
        "url": url,
        "domain": urlparse(url).netloc,
        "title": "",
        "description": "",
        "site_name": "",
        "canonical_url": "",
        "content_type": "",
        "content": "",
        "headings": [],
        "table_preview": "",
        "key_links": [],
        "word_count": 0,
        "status": "ok",
        "error": None,
    }

    try:
        client_timeout = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(headers=HEADERS, timeout=client_timeout) as session:
            async with session.get(url, ssl=False, allow_redirects=True) as resp:
                result["content_type"] = (resp.headers.get("Content-Type") or "").lower()
                result["final_url"] = str(resp.url)
                if resp.status >= 400:
                    result["status"] = "error"
                    result["error"] = f"HTTP {resp.status}"
                    return result
                raw_bytes = await resp.read()
    except asyncio.TimeoutError:
        result["status"] = "timeout"
        result["error"] = "Request timed out"
        return result
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        return result

    content_type = result["content_type"]
    lowered_url = url.lower()

    if "application/pdf" in content_type or lowered_url.endswith(".pdf"):
        pdf_text = _extract_pdf_text(raw_bytes)
        if not pdf_text:
            result["status"] = "error"
            result["error"] = "PDF fetched but no readable text was extracted"
            return result
        result["content"] = pdf_text
        result["word_count"] = len(pdf_text.split())
        result["title"] = result["domain"] or "PDF Document"
        return result

    if "application/json" in content_type or lowered_url.endswith(".json"):
        json_text = _extract_json_text(raw_bytes)
        result["content"] = json_text
        result["word_count"] = len(json_text.split())
        result["title"] = result["domain"] or "JSON Document"
        return result

    if any(token in content_type for token in ("text/plain", "application/xml", "text/xml")):
        text = _truncate(raw_bytes.decode("utf-8", errors="ignore"), 12000)
        result["content"] = text
        result["word_count"] = len(text.split())
        result["title"] = result["domain"] or "Text Document"
        return result

    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        result["status"] = "unsupported"
        result["error"] = f"Content-Type not supported: {content_type or 'unknown'}"
        return result

    html = raw_bytes.decode("utf-8", errors="ignore")
    payload = _extract_html_payload(html, url)
    result.update(payload)
    if not result["content"].strip():
        result["status"] = "error"
        result["error"] = "No readable page content found"
    return result


def _build_analysis_prompt(page: dict, user_question: str = "") -> str:
    question = (user_question or "").strip() or "Analyze this page in detail."
    lower_question = question.lower()
    extraction_mode = any(hint in lower_question for hint in EXTRACTION_HINTS)

    headings = "\n".join(f"- {heading}" for heading in page.get("headings", [])[:10]) or "- None detected"
    links = "\n".join(
        f"- {item.get('text', 'Link')} -> {item.get('href', '')}"
        for item in page.get("key_links", [])[:8]
    ) or "- None detected"

    task_mode = (
        "The user is likely asking for exact extraction. Prioritize faithful extraction of names, numbers, lists, specs, prices, contact details, or structured facts."
        if extraction_mode
        else "The user is asking for strong comprehension. Prioritize the direct answer, then the most useful supporting detail."
    )

    return f"""You are TIFLO AI analyzing a live webpage.

USER REQUEST:
{question}

TASK MODE:
{task_mode}

PAGE SNAPSHOT:
- URL: {page.get('url')}
- Final URL: {page.get('final_url', page.get('url'))}
- Domain: {page.get('domain')}
- Title: {page.get('title') or 'Unknown'}
- Description: {page.get('description') or 'Unknown'}
- Site Name: {page.get('site_name') or 'Unknown'}
- Approximate Word Count: {page.get('word_count', 0)}

HEADINGS:
{headings}

KEY LINKS:
{links}

TABLE / STRUCTURED DATA PREVIEW:
{page.get('table_preview') or 'None found'}

PAGE CONTENT:
{page.get('content') or 'No readable content'}

RULES:
- Use ONLY the page evidence above.
- Distinguish direct page facts from any inference.
- If the page appears partial or dynamic, answer from what is visible instead of hallucinating.
- If the user asks for extraction, include an **Extracted Data** section with bullets.
- Keep the answer sharp, high-signal, and specific.

FORMAT:
## Direct Answer
2-4 lines answering the user's request immediately.

## Extracted Data
Bullet list of concrete data points, if any.

## Important Details
Bullet list of the most relevant supporting facts.

## Takeaway
One short closing takeaway.
"""


async def analyze_url(url: str, user_question: str = "") -> str:
    print(f"🔗 Analyzing URL: {url}")
    t0 = time.time()
    page = await fetch_url_content(url)

    if page["status"] != "ok":
        return (
            f"**Could not fetch the URL.**\n\n"
            f"- **URL:** `{url}`\n"
            f"- **Error:** {page['error']}\n\n"
            f"Please check if the page is public and try again."
        )

    prompt = _build_analysis_prompt(page, user_question)
    try:
        runtime_metrics.record_provider("groq")
        response = _groq.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.15,
        )
        analysis = response.choices[0].message.content
        print(f"✅ URL analyzed in {round(time.time() - t0, 2)}s total")
        return analysis
    except Exception as e:
        print(f"⚠️ Groq error during URL analysis: {e}")
        return f"**Fetched the page but failed to analyze it.**\n\nError: {e}"


async def analyze_url_stream(url: str, user_question: str = ""):
    yield "data: __STATUS__:🔗 Fetching webpage...\n\n"
    page = await fetch_url_content(url)
    if page["status"] != "ok":
        message = (
            f"**Could not fetch the URL.**\n\n"
            f"- **URL:** `{url}`\n"
            f"- **Error:** {page['error']}\n\n"
            f"Please check if the page is public and try again."
        )
        yield "data: " + message.replace("\n", "\\n") + "\n\n"
        yield "data: [DONE]\n\n"
        return

    yield "data: __STATUS__:🧠 Extracting insights...\n\n"
    prompt = _build_analysis_prompt(page, user_question)
    try:
        runtime_metrics.record_provider("groq")
        stream = _groq.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.15,
            stream=True,
        )
        for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            if token:
                yield "data: " + token.replace("\n", "\\n") + "\n\n"
    except Exception as e:
        yield "data: " + f"⚠️ URL analysis failed: {str(e)[:160]}".replace("\n", "\\n") + "\n\n"
    yield "data: [DONE]\n\n"


async def analyze_multiple_urls(urls: list[str], user_question: str = "") -> str:
    clean_urls = list(dict.fromkeys(urls))[:3]
    tasks = [analyze_url(url, user_question) for url in clean_urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output = []
    for url, result in zip(clean_urls, results):
        if isinstance(result, Exception):
            output.append(f"### 🔗 {url}\nError: {result}")
        else:
            output.append(f"### 🔗 {url}\n{result}")
    return "\n\n---\n\n".join(output)


if __name__ == "__main__":
    import sys

    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://en.wikipedia.org/wiki/Artificial_intelligence"
    result = asyncio.run(analyze_url(test_url))
    print(result)
