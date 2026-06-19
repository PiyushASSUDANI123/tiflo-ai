import asyncio
from typing import Optional
from fast_ai import ask_live_ai_parallel


async def ask_live_ai(question: str, search_query: Optional[str] = None):
    """
    Backward-compatible wrapper around the production fast_ai engine.
    Useful for quick local CLI testing without relying on legacy ollama flows.
    """
    resolved_query = (search_query or question or "").strip()
    if not resolved_query:
        return {"text": "No query provided.", "sources": []}

    return await ask_live_ai_parallel(question=question, search_query=resolved_query)


if __name__ == "__main__":
    user_question = "What are the latest features of the Apple M4 chip?"
    optimized_query = "Apple M4 chip latest features"
    result = asyncio.run(ask_live_ai(user_question, optimized_query))
    print("\n================ LIVE AI RESPONSE ================")
    print(result.get("text", ""))
    print("Sources:", result.get("sources", []))
    print("==================================================\n")
