"""
agents.py — Tiflo AI Tool Calling / Agent System
====================================================
Gives Tiflo AI real tools it can USE — not just talk about.
Each tool is a function the AI can invoke via Groq function calling.

Tools:
  - calculator     : Math expressions (safe eval)
  - code_runner    : Execute Python code in a sandbox
  - memory_search  : Search past conversations
  - web_search     : Real-time internet search (wraps fast_ai)
  - knowledge_search: Search Tiflo's knowledge base
"""

import os
import ast
import sys
import json
import time
import math
import asyncio
import traceback
import re
from io import StringIO
from groq import Groq
from dotenv import load_dotenv
from fast_ai import ask_live_ai_parallel
from runtime_state import runtime_metrics

load_dotenv()

_groq = Groq(api_key=os.getenv("GROQ_API_KEY"))
# Use high-capacity model for complex agent reasoning
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
MAX_AGENT_STEPS = 3

# ── Tool Definitions (Groq function calling format) ──────────
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate a mathematical expression. Use for any arithmetic, algebra, percentage, or unit conversion. Always use this for math instead of calculating in your head.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "The math expression to evaluate. Example: '(234 * 56) / 100', 'math.sqrt(144)', '2**10'"
                    }
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "code_runner",
            "description": "Handle explicit requests to execute Python code. The execution environment is currently disabled for security hardening, so use this tool to return a clear unavailability message instead of running code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Valid Python code to execute. Print results using print()."
                    }
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memory_search",
            "description": "Search Tiflo AI's memory for relevant past information, facts about Piyush, or the Assudani Group.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for in memory."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the live web for current facts, news, prices, updates, or recent public information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The exact thing to search on the web."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "knowledge_search",
            "description": "Search Tiflo AI's internal local knowledge and founder/company notes for relevant information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The thing to look up in internal knowledge."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Fetch real-time weather information for a specific city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The city to get weather for (e.g. 'Balotra', 'Mumbai', 'New York')."
                    }
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_crypto_price",
            "description": "Fetch the real-time price of a cryptocurrency in USD (e.g., BTC, ETH, SOL).",
            "parameters": {
                "type": "object",
                "properties": {
                    "coin": {
                        "type": "string",
                        "description": "The cryptocurrency symbol (e.g., 'BTC', 'ETH', 'SOL', 'DOGE')."
                    }
                },
                "required": ["coin"]
            }
        }
    }
]


# ── Tool Implementations ─────────────────────────────────────


def _tool_calculator(expression: str) -> str:
    """Safe math evaluator using a strict AST whitelist."""
    allowed_constants = {
        "pi": math.pi,
        "e": math.e,
        "tau": math.tau,
    }
    allowed_functions = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
        "exp": math.exp,
        "floor": math.floor,
        "ceil": math.ceil,
        "factorial": math.factorial,
        "pow": pow,
    }
    allowed_binops = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
        ast.FloorDiv: lambda a, b: a // b,
        ast.Mod: lambda a, b: a % b,
        ast.Pow: lambda a, b: a ** b,
    }
    allowed_unary = {
        ast.UAdd: lambda a: +a,
        ast.USub: lambda a: -a,
    }

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name) and node.id in allowed_constants:
            return allowed_constants[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in allowed_binops:
            return allowed_binops[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in allowed_unary:
            return allowed_unary[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                fn_name = node.func.id
            elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "math":
                fn_name = node.func.attr
            else:
                raise ValueError("Unsafe function call")

            if fn_name not in allowed_functions:
                raise ValueError(f"Function '{fn_name}' is not allowed")

            args = [_eval(arg) for arg in node.args]
            return allowed_functions[fn_name](*args)

        raise ValueError("Unsupported expression")

    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval(tree)
        return f"Result: {result}"
    except ZeroDivisionError:
        return "Error: Division by zero"
    except Exception as e:
        return f"Calculation error: {e}"



def _tool_code_runner(code: str) -> str:
    """Code execution is disabled until a real sandbox is in place."""
    return (
        "Code execution is temporarily disabled for security hardening. "
        "I can still review, explain, or rewrite the code safely."
    )



def _tool_memory_search(query: str, user_id: str = "guest") -> str:
    """Search recent Firestore-backed memory without the missing rag_engine module."""
    try:
        from memory_db import get_recent_context

        context = get_recent_context(user_id=user_id, limit=10)
        if not context:
            return "Nothing relevant found in memory."

        terms = [term for term in re.findall(r"[a-zA-Z0-9_]+", query.lower()) if len(term) > 2]
        chunks = [chunk.strip() for chunk in context.split("\n---\n") if chunk.strip()]
        if not terms:
            return "Found in memory:\n" + "\n---\n".join(chunks[:3])

        scored = []
        for chunk in chunks:
            lower_chunk = chunk.lower()
            score = sum(lower_chunk.count(term) for term in terms)
            if score:
                scored.append((score, chunk))

        if not scored:
            return "Found in memory:\n" + "\n---\n".join(chunks[:3])

        scored.sort(key=lambda item: item[0], reverse=True)
        best = [chunk for _, chunk in scored[:3]]
        return "Found in memory:\n" + "\n---\n".join(best)
    except Exception as e:
        return f"Memory search error: {e}"


def _score_text_chunks(query: str, chunks: list[str], limit: int = 3) -> list[str]:
    terms = [term for term in re.findall(r"[a-zA-Z0-9_]+", query.lower()) if len(term) > 2]
    if not terms:
        return chunks[:limit]

    scored = []
    for chunk in chunks:
        lower_chunk = chunk.lower()
        score = sum(lower_chunk.count(term) for term in terms)
        if score:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in scored[:limit]]


async def _tool_web_search(query: str) -> str:
    """Search the live web and return a condensed answer plus source list."""
    result = await ask_live_ai_parallel(query, query)
    if not isinstance(result, dict):
        return str(result)

    text = str(result.get("text", "")).strip()
    sources = result.get("sources", []) or []
    source_lines = []
    for source in sources[:4]:
        title = source.get("title", "Web Result")
        url = source.get("url", "")
        source_lines.append(f"- {title}: {url}")

    if source_lines:
        return f"{text}\n\nSources:\n" + "\n".join(source_lines)
    return text or "No useful live web result found."


def _tool_knowledge_search(query: str, user_id: str = "guest") -> str:
    """Search local company knowledge and recent memory together."""
    knowledge_chunks = []

    try:
        company_data_path = os.path.join(os.path.dirname(__file__), "company_data.txt")
        with open(company_data_path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        if raw:
            knowledge_chunks.extend([chunk.strip() for chunk in raw.split("\n\n") if chunk.strip()])
    except Exception as e:
        knowledge_chunks.append(f"Local knowledge read error: {e}")

    memory_text = _tool_memory_search(query, user_id=user_id)
    if memory_text and not memory_text.lower().startswith("memory search error"):
        knowledge_chunks.extend([chunk.strip() for chunk in memory_text.split("\n---\n") if chunk.strip()])

    if not knowledge_chunks:
        return "No internal knowledge found."

    best = _score_text_chunks(query, knowledge_chunks, limit=4)
    if not best:
        best = knowledge_chunks[:4]
    return "Relevant internal knowledge:\n" + "\n---\n".join(best)

def _tool_get_weather(city: str) -> str:
    """Fetch real-time weather information for a specific city via wttr.in."""
    try:
        import requests
        print(f"🔧 Tool Execution: Fetching weather for '{city}'...")
        res = requests.get(f"https://wttr.in/{city}?format=3", timeout=5)
        if res.status_code == 200:
            return f"Weather in {city}: {res.text.strip()}"
        return f"Failed to get weather for {city} (Status: {res.status_code})"
    except Exception as e:
        return f"Weather API error: {e}"


def _tool_fetch_crypto_price(coin: str) -> str:
    """Fetch real-time cryptocurrency USD price via Binance public ticker API."""
    try:
        import requests
        symbol = coin.upper().strip()
        print(f"🔧 Tool Execution: Fetching crypto rate for '{symbol}'...")
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        res = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=5)
        if res.status_code == 200:
            data = res.json()
            price = float(data.get("price", 0))
            return f"Current price of {coin.upper()}: ${price:,.2f} USD (Source: Binance)"
        return f"Failed to find crypto rate for '{coin}'. Make sure to use symbols like BTC, ETH, SOL, or DOGE."
    except Exception as e:
        return f"Crypto API error: {e}"


# ── Main Agent Runner ────────────────────────────────────────
async def run_agent(
    user_message: str,
    conversation_history: list,
    system_prompt: dict,
    user_id: str = "guest"
):
    """
    Multi-step agentic loop — AI can call tools, inspect results, and continue
    reasoning for a few rounds before producing the final answer.
    Yields SSE-formatted tokens just like master.py streaming.
    """
    messages = conversation_history + [{"role": "user", "content": user_message}]
    if messages[0]["role"] != "system":
        messages.insert(0, system_prompt)

    try:
        for step in range(MAX_AGENT_STEPS):
            runtime_metrics.record_provider("groq")
            response = _groq.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                temperature=0.1
            )

            msg = response.choices[0].message
            tool_calls = msg.tool_calls or []

            if not tool_calls:
                content = msg.content or ""
                i = 0
                chunk_size = 4
                while i < len(content):
                    chunk = content[i:i+chunk_size]
                    safe = chunk.replace('\n', '\\n')
                    yield f"data: {safe}\n\n"
                    await asyncio.sleep(0.005)
                    i += chunk_size
                return

            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            })

            yield f"data: ⚙️ Agent step {step + 1}/{MAX_AGENT_STEPS}: checking tools...\\n\\n\n\n"
            await asyncio.sleep(0.05)

            for tc in tool_calls:
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments)
                runtime_metrics.record_tool(fn_name)

                print(f"🔧 Agent calling tool: {fn_name}({fn_args})")
                yield f"data: ⚙️ Using tool: **{fn_name}**...\\n\\n\n\n"
                await asyncio.sleep(0.05)

                if fn_name == "calculator":
                    result = _tool_calculator(fn_args.get("expression", ""))
                elif fn_name == "code_runner":
                    result = _tool_code_runner(fn_args.get("code", ""))
                elif fn_name == "memory_search":
                    result = await asyncio.to_thread(_tool_memory_search, fn_args.get("query", ""), user_id)
                elif fn_name == "web_search":
                    result = await _tool_web_search(fn_args.get("query", ""))
                elif fn_name == "knowledge_search":
                    result = await asyncio.to_thread(_tool_knowledge_search, fn_args.get("query", ""), user_id)
                elif fn_name == "get_weather":
                    result = await asyncio.to_thread(_tool_get_weather, fn_args.get("city", ""))
                elif fn_name == "fetch_crypto_price":
                    result = await asyncio.to_thread(_tool_fetch_crypto_price, fn_args.get("coin", ""))
                else:
                    result = f"Unknown tool: {fn_name}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        messages.append({
            "role": "system",
            "content": (
                "You have reached the tool budget. Do not call more tools. "
                "Use the gathered tool results to produce the best final answer."
            ),
        })

        runtime_metrics.record_provider("groq")
        final_stream = _groq.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.1,
            stream=True
        )

        for chunk in final_stream:
            token = chunk.choices[0].delta.content or ""
            if token:
                safe = token.replace('\n', '\\n')
                yield f"data: {safe}\n\n"

    except Exception as e:
        print(f"⚠️ Agent error: {e}")
        traceback.print_exc()
        yield f"data: ⚠️ Agent encountered an error: {str(e)}\\n\n\n"
