import asyncio
import hashlib
import json
import os
import time
from urllib.parse import urlparse

from dotenv import load_dotenv
from duckduckgo_search import DDGS
from groq import Groq

from runtime_state import followup_cache, runtime_metrics, search_cache
from url_analyzer import fetch_url_content

load_dotenv()
_groq = Groq(api_key=os.getenv("GROQ_API_KEY"))
# Using 70B for deeper intelligence in parallel tasks
_GROQ_MODEL = "llama-3.3-70b-versatile"


def _normalize_query(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _query_variants(question: str, search_query: str) -> list[str]:
    variants = []
    for candidate in [search_query, question, f"{search_query} latest", f"{question} latest"]:
        clean = _normalize_query(candidate)
        if not clean:
            continue
        if clean.lower() in {item.lower() for item in variants}:
            continue
        variants.append(clean)
    return variants[:3]


def _result_url(item: dict) -> str:
    return (item.get("href") or item.get("url") or "").strip()


def _result_title(item: dict) -> str:
    return (item.get("title") or item.get("source") or "Web Result").strip()


def _result_snippet(item: dict) -> str:
    return (item.get("body") or item.get("excerpt") or item.get("description") or "").strip()


def _dedupe_results(results: list[dict], limit: int = 6) -> list[dict]:
    deduped = []
    seen = set()
    for item in results:
        url = _result_url(item)
        if not url:
            continue
        key = url.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def search_internet(query: str, extra_queries: list[str] | None = None, max_results: int = 6) -> list[dict]:
    search_queries = _query_variants(extra_queries[0] if extra_queries else query, query)
    if extra_queries:
        for candidate in extra_queries[1:]:
            clean = _normalize_query(candidate)
            if clean and clean.lower() not in {item.lower() for item in search_queries}:
                search_queries.append(clean)

    print(f"🌍 Live Search: {search_queries}")
    collected: list[dict] = []

    for candidate in search_queries[:3]:
        try:
            with DDGS() as ddgs:
                collected.extend(list(ddgs.text(candidate, max_results=4)))
        except Exception as e:
            print(f"⚠️ DDGS text search failed for '{candidate}': {e}")

        try:
            with DDGS() as ddgs:
                collected.extend(list(ddgs.news(candidate, max_results=3)))
        except Exception as e:
            print(f"⚠️ DDGS news search failed for '{candidate}': {e}")

    results = _dedupe_results(collected, limit=max_results)
    print(f"✅ Search deduped to {len(results)} results.")
    return results


def extract_ddgs_snippets(search_results: list[dict]) -> str:
    sections = []
    for idx, item in enumerate(search_results[:6], start=1):
        title = _result_title(item)
        body = _result_snippet(item)
        url = _result_url(item)
        published = item.get("date") or item.get("published") or item.get("published_date") or ""
        published_line = f"Date: {published}\n" if published else ""
        if url:
            sections.append(
                f"[Source {idx}] {title} ({url})\n"
                f"{published_line}"
                f"Snippet: {body or 'No snippet available.'}"
            )
    return "\n\n".join(sections)


async def fetch_and_package(url: str, idx: int) -> str:
    print(f"🚀 Agent {idx} → {url}")
    page = await fetch_url_content(url, timeout=8)
    if page.get("status") != "ok" or not page.get("content"):
        return ""

    headings = "; ".join(page.get("headings", [])[:5])
    table_preview = page.get("table_preview", "")
    description = page.get("description", "")
    content = page.get("content", "")[:2600]

    blocks = [
        f"[Source {idx}] {page.get('title') or 'Untitled'} ({url})",
        f"Domain: {page.get('domain') or 'Unknown'}",
    ]
    if description:
        blocks.append(f"Description: {description}")
    if headings:
        blocks.append(f"Headings: {headings}")
    if table_preview:
        blocks.append(f"Structured Data:\n{table_preview}")
    blocks.append(f"Content:\n{content}")
    print(f"✅ Agent {idx} packaged {len(content)} chars")
    return "\n".join(blocks)


async def ask_live_ai_parallel(question: str, search_query: str):
    start_time = time.time()
    cache_key = hashlib.sha256(f"{question.strip()}||{search_query.strip()}".encode("utf-8")).hexdigest()
    cached = search_cache.get(cache_key)
    if cached:
        runtime_metrics.record_cache_hit("search")
        yield {"status": "Retrieving cached research..."}
        yield cached
        return
    runtime_metrics.record_cache_miss("search")

    yield {"status": f"Searching Google for '{search_query}'..."}
    search_results = await asyncio.to_thread(
        search_internet,
        search_query,
        [question, search_query],
        6,
    )
    if not search_results:
        yield {"status": "Fallback to internal knowledge..."}
        try:
            fallback_response = _groq.chat.completions.create(
                model=_GROQ_MODEL,
                messages=[{"role": "system", "content": "You are TIFLO AI. Answer the user directly."}, {"role": "user", "content": question}],
                temperature=0.7,
            )
            ai_text = fallback_response.choices[0].message.content
            yield {"text": ai_text, "sources": []}
        except Exception as e:
            yield {"text": f"❌ Could not retrieve live results. Fallback failed: {e}", "sources": []}
        return

    snippet_context = extract_ddgs_snippets(search_results)
    print(f"⚡ Snippets ready in {round(time.time() - start_time, 2)}s")

    scraped_context = ""
    urls = [_result_url(item) for item in search_results if _result_url(item)]
    if urls:
        for idx, url in enumerate(urls[:5], start=1):
            domain = urlparse(url).netloc.replace('www.', '')
            yield {"status": f"Reading {domain}..."}

        tasks = [asyncio.create_task(fetch_and_package(url, idx)) for idx, url in enumerate(urls[:5], start=1)]
        done, pending = await asyncio.wait(tasks, timeout=4.5)
        for task in pending:
            task.cancel()
        for task in done:
            try:
                result = task.result()
            except Exception:
                result = ""
            if result:
                scraped_context += result + "\n\n"

    yield {"status": "Synthesizing evidence..."}
    combined_context = scraped_context.strip()
    if snippet_context:
        combined_context += ("\n\n--- Search Snippets ---\n" if combined_context else "") + snippet_context

    if not combined_context.strip():
        yield {"text": "I couldn't retrieve enough live context for this query.", "sources": []}
        return

    print(f"⏱️ Context ready in {round(time.time() - start_time, 2)}s ({len(combined_context)} chars)")

    final_prompt = f"""You are TIFLO AI, a research-grade live answer engine.
Today: {time.strftime('%d %B %Y')}, {time.strftime('%H:%M')} IST

Use ONLY the live evidence below to answer the user's question.

QUALITY BAR:
- Answer like a strong real-time research assistant.
- Lead with the direct answer immediately.
- Surface the most important verified facts first.
- If multiple sources disagree, say that clearly and prefer the strongest or most recent evidence.
- Never invent prices, dates, names, or numbers.

CITATION RULES:
- Every factual claim must end with inline source tags like [1], [2], or [1][3].
- Do NOT add a separate sources section at the end.

FORMAT:
- Start with one **bold** direct answer line.
- Then provide concise bullets with the most relevant facts.
- If uncertainty remains, add one short line starting with **Watch-out:**.

LIVE EVIDENCE:
{combined_context}

User Question: {question}
Answer:"""

    try:
        runtime_metrics.record_provider("groq")
        response = _groq.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[{"role": "user", "content": final_prompt}],
            temperature=0.12,
        )
        ai_text = response.choices[0].message.content

        sources = []
        for idx, item in enumerate(search_results[:5], start=1):
            url = _result_url(item)
            if not url:
                continue
            sources.append(
                {
                    "id": idx,
                    "title": _result_title(item),
                    "url": url,
                    "snippet": _result_snippet(item)[:240],
                    "domain": urlparse(url).netloc,
                    "published": item.get("date") or item.get("published") or item.get("published_date") or "",
                }
            )

        payload = {"text": ai_text, "sources": sources}
        search_cache.set(cache_key, payload)
        print(f"✅ Real-time response ready in {round(time.time() - start_time, 2)}s")
        yield payload
    except Exception as e:
        print(f"⚠️ LLM Error: {e}")
        yield {"text": "There was an internal error communicating with Groq.", "sources": []}


async def generate_followups(question: str, answer: str) -> list[str]:
    cache_key = hashlib.sha256(f"{question.strip()}||{answer[:700].strip()}".encode("utf-8")).hexdigest()
    cached = followup_cache.get(cache_key)
    if cached:
        runtime_metrics.record_cache_hit("followups")
        return cached
    runtime_metrics.record_cache_miss("followups")

    prompt = f"""Based on this Q&A, generate exactly 3 short, specific follow-up questions the user might want next.

User asked: {question}
AI answered: {answer[:700]}

Rules:
- Keep each question under 12 words
- Make them concrete and useful
- Output ONLY JSON like: {{\"questions\": [\"Q1\", \"Q2\", \"Q3\"]}}"""

    try:
        runtime_metrics.record_provider("groq")
        response = _groq.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=150,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response.choices[0].message.content)
        result = [str(item) for item in parsed.get("questions", [])[:3]]
        followup_cache.set(cache_key, result)
        return result
    except Exception as e:
        print(f"⚠️ Follow-ups generation failed: {e}")
        return []


if __name__ == "__main__":
    async def run_test():
        q = "What is the weather today in Mumbai?"
        query = "Mumbai weather today current temperature"
        async for chunk in ask_live_ai_parallel(q, query):
            print(chunk)
    asyncio.run(run_test())
