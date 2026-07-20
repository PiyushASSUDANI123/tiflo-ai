import json
import os
import re

from dotenv import load_dotenv
from groq import Groq

from runtime_state import router_cache, runtime_metrics

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
# Using the most capable model for highly accurate semantic routing
GROQ_MODEL = "llama-3.3-70b-versatile"

URL_PATTERN = re.compile(r'https?://[^\s<>"\')\]`]+', re.IGNORECASE)
MATH_EXPRESSION_PATTERN = re.compile(r"^[\d\s\+\-\*/%\(\)\.\^,]+$")

URL_INTENT_HINTS = [
    "summarize",
    "summary",
    "analyze",
    "analyse",
    "extract",
    "read",
    "review",
    "break down",
    "what is on",
    "what's on",
    "what is in",
    "what's in",
    "what does this say",
    "explain this link",
    "explain this page",
    "from this website",
    "from this page",
    "from this link",
    "website",
    "webpage",
    "page",
    "site",
    "link",
    "article",
    "blog",
    "repo",
    "repository",
    "documentation",
    "docs",
]

WEB_SEARCH_KEYWORDS = [
    "latest news",
    "kya hua aaj",
    "aaj ki khabar",
    "today news",
    "current news",
    "breaking news",
    "who won",
    "live score",
    "ipl score",
    "cricket score",
    "match score",
    "stock price",
    "share price",
    "abhi kya chal raha",
    "right now happening",
    "what is happening now",
]

WEB_SEARCH_LOOSE = [
    "news",
    "khabar",
    "latest",
    "score",
    "live",
]

UI_GENERATOR_ACTIONS = [
    "build",
    "create",
    "generate",
    "make",
    "design",
    "craft",
    "give me",
]

UI_GENERATOR_TARGETS = [
    "tailwind",
    "semantic html",
    "html and tailwind",
    "pricing card",
    "glassmorphism",
    "bento grid",
    "hero section",
    "landing page",
    "navbar",
    "dashboard card",
    "ui component",
    "ui block",
    "portfolio section",
    "copy-paste ui",
]

COLD_OUTREACH_KEYWORDS = [
    "cold dm",
    "cold email",
    "cold message",
    "client outreach",
    "outreach message",
    "sales pitch",
    "pitch message",
    "prospecting",
    "lead generation",
    "agency owner",
    "appointment setter",
    "book meetings",
]

ASO_KEYWORDS = [
    "aso",
    "app store",
    "play store",
    "store listing",
    "app description",
    "short description",
    "release notes",
    "what's new",
    "app metadata",
    "keyword optimization",
    "store keywords",
    "launch kit",
]

TEACH_KEYWORDS = [
    "explain me",
    "explain karo",
    "explain kar",
    "mujhe samjhao",
    "samjhao",
    "samjha do",
    "sikhao",
    "mujhe sikha",
    "padha do",
    "padha",
    "sikha",
    "concept explain",
    "concept kya hai",
    "theory kya hai",
    "nahi samajh aaya",
    "samajh nahi aaya",
    "mujhe nahi pata",
    "easy mein batao",
    "simple mein batao",
    "desi mein samjhao",
    "backbencher mode",
    "guru mode",
    "step by step explain",
    "solve karo step",
    "solve step by step",
    "kaise karte hain",
    "basics samjhao",
    "introduction to",
    "fundamentals of",
    "beginner guide",
    "for beginners",
]

AGENT_KEYWORDS = [
    "calculate",
    "run code",
    "execute code",
    "solve math",
    "compute",
    "run this",
    "execute this",
    "crypto price",
    "bitcoin price",
    "btc price",
    "eth price",
    "solana price",
    "doge price",
    "current price of",
    "rate of bitcoin",
    "rate of btc",
    "weather in",
    "mausam in",
    "temperature in",
    "will it rain in",
]

GREETING_KEYWORDS = [
    "hey",
    "hi",
    "hello",
    "hola",
    "namaste",
    "kem cho",
    "kaise ho",
    "sup",
    "yo",
    "hiii",
    "heyy",
    "hellooo",
    "gm",
    "gn",
    "good morning",
    "good night",
    "good evening",
    "wassup",
    "kya haal",
    "kya chal raha",
]

SHORT_WEB_SEARCH_PATTERNS = [
    re.compile(r"^(latest|today|current|breaking)\b", re.IGNORECASE),
    re.compile(r"\b(news|score|price|weather)\b", re.IGNORECASE),
    re.compile(r"\b(btc|bitcoin|eth|ethereum|sol|solana|doge|gold|nifty|sensex)\b", re.IGNORECASE),
]

SHORT_AGENT_PATTERNS = [
    re.compile(r"^\s*\d[\d\s\+\-\*/%\(\)\.]*\s*$"),
    re.compile(r"^(calculate|compute|solve)\b", re.IGNORECASE),
]


def _contains_url(user_prompt: str) -> list[str]:
    return URL_PATTERN.findall(user_prompt or "")


def _wants_url_analysis(user_prompt: str, urls: list[str]) -> bool:
    if not urls:
        return False

    lower = (user_prompt or "").lower()
    stripped = (user_prompt or "").strip()
    cleaned = stripped.strip('"\'[]()<>`')

    if len(urls) == 1 and cleaned == urls[0]:
        return True

    if any(hint in lower for hint in URL_INTENT_HINTS):
        return True

    for url in urls:
        residual = stripped.replace(url, " ").strip()
        if residual:
            return True

    return False


def _is_high_signal_short_prompt(lower: str) -> bool:
    return any(pattern.search(lower) for pattern in SHORT_WEB_SEARCH_PATTERNS + SHORT_AGENT_PATTERNS)


def _contains_any_phrase(lower: str, phrases: list[str]) -> bool:
    return any(phrase in lower for phrase in phrases)


def _specialty_check(user_prompt: str):
    lower = (user_prompt or "").lower().strip()
    word_count = len(lower.split())

    ui_hit = _contains_any_phrase(lower, UI_GENERATOR_TARGETS)
    ui_action = _contains_any_phrase(lower, UI_GENERATOR_ACTIONS)
    ui_explainer = any(lower.startswith(prefix) for prefix in ("what is ", "what's ", "explain ", "how does "))
    if ui_hit and not ui_explainer and (
        ui_action
        or "copy-paste" in lower
        or "copy paste" in lower
        or word_count <= 18
        or " with " in lower
    ):
        print("🎨 Premium UI generation request detected → UI_GENERATOR")
        return {
            "intent": "UI_GENERATOR",
            "reason": "premium-ui-component-request",
            "search_query": "",
        }

    cold_hit = _contains_any_phrase(lower, COLD_OUTREACH_KEYWORDS)
    if cold_hit or (
        any(token in lower for token in ("client", "business", "prospect", "lead"))
        and any(token in lower for token in ("dm", "email", "outreach", "pitch"))
    ):
        print("🧲 Cold outreach request detected → COLD_OUTREACH")
        return {
            "intent": "COLD_OUTREACH",
            "reason": "cold-outreach-request",
            "search_query": "",
        }

    aso_hit = _contains_any_phrase(lower, ASO_KEYWORDS)
    if aso_hit or (
        "app" in lower
        and any(token in lower for token in ("play store", "app store", "release note", "description", "keywords"))
    ):
        print("🚀 App store launch request detected → ASO_LAUNCH_KIT")
        return {
            "intent": "ASO_LAUNCH_KIT",
            "reason": "aso-launch-request",
            "search_query": "",
        }

    return None


def _looks_like_math_request(user_prompt: str) -> bool:
    lower = (user_prompt or "").strip().lower()
    if any(lower.startswith(prefix) for prefix in ("calculate ", "compute ", "solve ")):
        return True
    return bool(MATH_EXPRESSION_PATTERN.fullmatch(lower))


def _url_check(user_prompt: str):
    urls = _contains_url(user_prompt)
    if _wants_url_analysis(user_prompt, urls):
        if len(urls) == 1 and user_prompt.strip().strip('"\'[]()<>`') == urls[0]:
            print(f"🔗 Raw URL detected: {urls[0]} → URL_ANALYSIS")
        else:
            print(f"🔗 URL + analysis request detected ({len(urls)} URL(s)) → URL_ANALYSIS")
        return {
            "intent": "URL_ANALYSIS",
            "reason": f"URL content request detected ({len(urls)} URL(s))",
            "urls": urls,
            "search_query": "",
        }
    return None


def _keyword_check(user_prompt: str):
    lower = user_prompt.lower().strip()
    word_count = len(lower.split())

    if word_count <= 3 and not _is_high_signal_short_prompt(lower):
        return None

    for kw in TEACH_KEYWORDS:
        if kw in lower:
            print(f"📚 Keyword match '{kw}' → TEACH (Guru Mode)")
            return {"intent": "TEACH", "reason": f"Keyword '{kw}' matched", "search_query": ""}

    for kw in AGENT_KEYWORDS:
        if kw in lower:
            print(f"🔧 Keyword match '{kw}' → AGENT (Autonomous Agent)")
            return {"intent": "AGENT", "reason": f"Keyword '{kw}' matched", "search_query": ""}

    for kw in WEB_SEARCH_KEYWORDS:
        if kw in lower:
            print(f"⚡ Keyword match '{kw}' → WEB_SEARCH (no LLM needed)")
            return {"intent": "WEB_SEARCH", "reason": f"Keyword '{kw}' matched", "search_query": user_prompt}

    words = lower.split()
    for kw in WEB_SEARCH_LOOSE:
        if words and (words[0] == kw or (len(words) > 1 and words[1] == kw)):
            print(f"⚡ Loose keyword '{kw}' at start → WEB_SEARCH")
            return {
                "intent": "WEB_SEARCH",
                "reason": f"Loose keyword '{kw}' matched at start",
                "search_query": user_prompt,
            }

    return None


def _greeting_check(user_prompt: str):
    lower = user_prompt.lower().strip()
    if lower in GREETING_KEYWORDS:
        print("👋 Greeting detected → CHIT_CHAT (instant)")
        return {"intent": "CHIT_CHAT", "reason": "greeting", "search_query": ""}
    return None


def _fallback_route(cleaned_prompt: str):
    greet_result = _greeting_check(cleaned_prompt)
    if greet_result:
        return greet_result

    specialty_result = _specialty_check(cleaned_prompt)
    if specialty_result:
        return specialty_result

    url_result = _url_check(cleaned_prompt)
    if url_result:
        return url_result

    kw_result = _keyword_check(cleaned_prompt)
    if kw_result:
        kw_result["search_query"] = cleaned_prompt
        return kw_result

    if _looks_like_math_request(cleaned_prompt):
        return {"intent": "AGENT", "reason": "math-expression-fallback", "search_query": ""}

    return {"intent": "CHIT_CHAT", "reason": "fallback-default", "search_query": cleaned_prompt}


def ai_router(user_prompt, conversation_history=None):
    conversation_history = conversation_history or []
    cleaned_prompt = user_prompt
    if "User Query:" in user_prompt:
        cleaned_prompt = user_prompt.split("User Query:", 1)[1].strip()

    context_snippet = ""
    for msg in conversation_history[-4:]:
        context_snippet += f"{msg['role'].upper()}: {msg['content']}\n"

    cache_key = f"{cleaned_prompt.strip().lower()}::{context_snippet.strip().lower()}"
    cached = router_cache.get(cache_key)
    if cached:
        runtime_metrics.record_cache_hit("router")
        return cached
    runtime_metrics.record_cache_miss("router")

    greet_result = _greeting_check(cleaned_prompt)
    if greet_result:
        router_cache.set(cache_key, greet_result, ttl=300)
        return greet_result

    specialty_result = _specialty_check(cleaned_prompt)
    if specialty_result:
        router_cache.set(cache_key, specialty_result, ttl=300)
        return specialty_result

    url_result = _url_check(cleaned_prompt)
    if url_result:
        router_cache.set(cache_key, url_result, ttl=300)
        return url_result

    kw_result = _keyword_check(cleaned_prompt)
    if kw_result:
        kw_result["search_query"] = cleaned_prompt
        router_cache.set(cache_key, kw_result, ttl=300)
        return kw_result

    system_prompt = f"""You are a precise intent classifier for an AI assistant. Output ONLY raw JSON. No markdown, no explanation.

INTENT DEFINITIONS — Read carefully before classifying:

1. CHIT_CHAT (DEFAULT):
   - Any general question, explanation request, concept query, opinion, advice, writing help, coding help, language/grammar, life advice, creative request, or casual conversation.
   - This is the MOST COMMON intent. Use it for ANY message that does not clearly fit the others below.

2. WEB_SEARCH:
   - For real-time / live information that changes daily: breaking news, live scores, today's stock prices, current events.
   - CRITICAL: Use WEB_SEARCH for ANY factual question about specific people, celebrities, places, events, or things that require highly accurate or historical facts.
   - If the user asks a factual question that might require external knowledge (like "what is X" or "tell me about Y" where Y is not a general coding concept), choose WEB_SEARCH to ensure accuracy.

3. AGENT:
   - ONLY for explicit tool use: executing code, calculating a math expression, checking live crypto/stock price, real-time weather.

4. LOCAL_DB:
   - Questions specifically about Piyush Assudani, Assudani Group, Tiflo AI's own features/team/history.

5. URL_ANALYSIS:
   - ONLY when the user provides a URL AND asks something about its content.

6. UI_GENERATOR:
   - For premium frontend component requests like Tailwind blocks, pricing cards, landing sections, glassmorphism, bento grids, or copy-paste HTML UI generation.

7. COLD_OUTREACH:
   - For cold emails, cold DMs, agency outreach, pitch messages, or client acquisition messaging.

8. ASO_LAUNCH_KIT:
   - For App Store / Play Store descriptions, keyword packs, store metadata, or release-note generation.

CRITICAL RULES:
- CHIT_CHAT is the DEFAULT. When in doubt → CHIT_CHAT.
- Do NOT choose WEB_SEARCH for general knowledge or explanations.
- Do NOT choose AGENT unless the user is clearly asking to RUN or CALCULATE something right now.
- Use UI_GENERATOR when the user clearly wants a copy-pasteable premium UI block, not a generic coding explanation.
- Use COLD_OUTREACH when the user wants persuasive outbound messaging, not general writing help.
- Use ASO_LAUNCH_KIT when the user wants app listing assets or store optimization deliverables.
- Fix typos in search_query. Resolve pronouns using context.

RECENT CONTEXT (last few turns):
{context_snippet}
"""

    try:
        runtime_metrics.record_provider("groq")
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": cleaned_prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )

        raw_output = response.choices[0].message.content.strip()
        clean_json = re.sub(r"^```json\s*|```$", "", raw_output, flags=re.MULTILINE)
        result = json.loads(clean_json)
        print(f"🎯 Router → {result.get('intent')} | Reason: {result.get('reason')}")
        router_cache.set(cache_key, result)
        return result

    except Exception as e:
        print(f"⚠️ Router Error: {e}. Falling back to deterministic routing.")
        fallback = _fallback_route(cleaned_prompt)
        router_cache.set(cache_key, fallback, ttl=60)
        return fallback
