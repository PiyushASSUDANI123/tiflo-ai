from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Request
import mimetypes
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from master import stream_altair_response, groq_client
from image_analyzer import analyze_image_stream, encode_file_to_base64
from url_analyzer import analyze_url_stream, analyze_multiple_urls, extract_urls
from memory_db import save_interaction, save_feedback, save_shared_chat, get_shared_chat, get_all_chats, get_memory_stats
from auth import VerifiedIdentity, verify_request_identity
from credit_manager import (
    ConcurrentHitError,
    InsufficientCreditsError,
    claim_hit,
    create_razorpay_placeholder_order,
    ensure_user_account,
    finish_hit,
    initialize_credit_store,
    release_stuck_hits,
)
from firebase_setup import DEFAULT_LOGIN_CREDITS, FOUNDER_EMAIL, get_firebase_public_config
from runtime_state import runtime_metrics, router_cache, summary_cache, search_cache, followup_cache
import requests
import asyncio
import time
import os
import json
from dotenv import load_dotenv
from slowapi.util import get_remote_address

load_dotenv()

# Initialize Rate Limiter
app = FastAPI(title="TIFLO AI CORE")
initialize_credit_store()
recovered_hits = release_stuck_hits()
if recovered_hits:
    print(f"♻️ Recovered {recovered_hits} stale in-progress credit hit(s).")

# Rate limit exception handler - security first!

def _build_allowed_origins() -> list[str]:
    default_origins = [
        "https://tiflo.in",
        "https://www.tiflo.in",
        "https://mancho.pages.dev",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:5501",
        "http://127.0.0.1:5501",
        "http://localhost:7860",
        "http://127.0.0.1:7860",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "null",
    ]
    extra = [
        origin.strip()
        for origin in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
        if origin.strip()
    ]
    merged = []
    seen = set()
    for origin in default_origins + extra:
        if origin not in seen:
            seen.add(origin)
            merged.append(origin)
    return merged


app.add_middleware(
    CORSMiddleware,
    allow_origins=_build_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class FeedbackRequest(BaseModel):
    user_id: str
    chat_id: str
    feedback_type: str
    feedback_text: str = ""
    last_user_message: str = ""
    last_ai_message: str = ""

class ShareChatRequest(BaseModel):
    messages: list
    title: str = "Shared Chat"

class ChatRequest(BaseModel):
    message: str
    history: list = Field(default_factory=list)
    user_id: str = "guest"
    user_email: str = ""     # Legacy client field — never trusted for auth
    user_name: str = ""      # Used only as a display-name hint alongside a verified Firebase token
    image_data: str = ""   # base64 data URI or image URL (optional)
    mode: str = "default"  # active AI mode
    use_openrouter: bool = False
    deep_search: bool = False
    is_incognito: bool = False
    location: str = ""


class UrlAnalysisRequest(BaseModel):
    url: str
    question: str = ""
    user_id: str = "guest"


class RazorpayOrderRequest(BaseModel):
    plan_code: str = "starter_topup"
    credits_pack: int = 0
    amount_paise: int = 0
    user_id: str = "guest"


def _validate_history_payload(history: list):
    for idx, item in enumerate(history or []):
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail=f"History item {idx + 1} must be an object.")
        role = str(item.get("role", "")).strip().lower()
        if role not in {"system", "user", "assistant"}:
            raise HTTPException(status_code=400, detail=f"History item {idx + 1} has invalid role '{role}'.")
        content = str(item.get("content", ""))
        if len(content) > 16000:
            raise HTTPException(status_code=400, detail=f"History item {idx + 1} is too large.")


def _account_event_payload(snapshot: dict) -> str:
    # Firebase suspended — emit nothing to clients
    return ""


def _build_charge_headers(snapshot: dict) -> dict:
    return {
        "X-Auth-Provider": "none",
        "X-Unlimited-Access": "true",
        "X-Credits-Remaining": "unlimited",
    }


def _require_identity(request: Request, claimed_user_id: str = "", claimed_user_name: str = "") -> VerifiedIdentity:
    identity = verify_request_identity(
        request.headers.get("Authorization", ""),
        claimed_user_id,
        claimed_user_name,
    )
    if not identity.is_authenticated:
        identity.user_id = claimed_user_id or "guest"
        identity.user_name = claimed_user_name or "Guest User"
    return identity


_DUMMY_SNAPSHOT = {
    "user_id": "guest",
    "email": "",
    "display_name": "Guest User",
    "remaining_credits": None,
    "unlimited_access": True,
    "is_guest": True,
}


def _ensure_account_for_identity(identity: VerifiedIdentity) -> dict:
    # Firebase suspended — return dummy snapshot
    return _DUMMY_SNAPSHOT


def _claim_metered_hit(identity: VerifiedIdentity, route: str) -> tuple[str, dict]:
    # Firebase suspended — no metering, return dummy
    return "no-op", _DUMMY_SNAPSHOT


def _finalize_metered_hit(identity: VerifiedIdentity, request_id: str, ok: bool, error_message: str = "") -> dict:
    # Firebase suspended — return dummy snapshot
    return _DUMMY_SNAPSHOT


def _provider_error_message(exc: Exception) -> tuple[int, str]:
    text = str(exc).lower()
    if any(token in text for token in ("connection error", "timed out", "temporarily unavailable", "api key", "authentication")):
        return 503, "AI provider is temporarily unavailable. Please retry in a moment."
    return 500, "Backend hit an unexpected error while processing the request."


def _validate_chat_request(chat_req: ChatRequest):
    if not str(chat_req.message or "").strip() and not str(chat_req.image_data or "").strip():
        raise HTTPException(status_code=400, detail="Message or attachment required.")

    if len(str(chat_req.message or "")) > 12000:
        raise HTTPException(status_code=413, detail="Message too long. Keep it under 12,000 characters.")

    if len(chat_req.history or []) > 60:
        raise HTTPException(status_code=400, detail="Conversation history too large.")
    _validate_history_payload(chat_req.history)

    if len(str(chat_req.image_data or "")) > 20_000_000:
        raise HTTPException(status_code=413, detail="Attachment payload too large.")

    allowed_modes = {
        "default",
        "teach",
        "backbencher",
        "uncensored",
        "incognito",
        "ceo",
        "human",
        "ui_generator",
        "cold_outreach",
        "aso_launch_kit",
    }
    if chat_req.mode and chat_req.mode not in allowed_modes:
        raise HTTPException(status_code=400, detail=f"Unsupported mode '{chat_req.mode}'.")


def get_client_ip(request: Request) -> str:
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    cf_connecting_ip = request.headers.get("cf-connecting-ip")
    if cf_connecting_ip:
        return cf_connecting_ip.strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


def save_to_firebase_bg(user_message, ai_response, intent, user_id, user_email="", user_ip="", user_location="", model="lite", mode="default"):
    """Fire-and-forget Firebase save — runs in thread, never blocks API."""
    save_interaction(user_id, user_message, ai_response, intent, user_email, user_ip, user_location, model, mode)



def save_feedback_to_firebase_bg(user_id, chat_id, feedback_type, feedback_text, last_user_msg, last_ai_msg):
    save_feedback(user_id, chat_id, feedback_type, feedback_text, last_user_msg, last_ai_msg)


def _extract_persistable_payload(chunk: str) -> str:
    if not chunk.startswith("data: "):
        return ""

    payload = chunk[6:].strip()
    if (
        not payload
        or payload == "[DONE]"
        or payload.startswith("__STATUS__:")
        or payload.startswith("__ACCOUNT__:")
        or payload.startswith("__SOURCES__:")
        or payload.startswith("__FOLLOWUPS__:")
        or payload.startswith("⚙️")
    ):
        return ""

    return payload


def _payload_indicates_failed_run(payload: str) -> bool:
    failed_prefixes = (
        "⚠️",
        "**Could not fetch the URL.**",
        "**Fetched the page but failed to analyze it.**",
        "**Page fetched but no readable content found.**",
        "Error parsing PDF file:",
    )
    return any(payload.startswith(prefix) for prefix in failed_prefixes)


@app.post("/chat/stream")
async def chat_stream(request: Request, chat_req: ChatRequest):
    _validate_chat_request(chat_req)
    effective_use_openrouter = chat_req.use_openrouter or chat_req.mode == "uncensored"
    effective_incognito = chat_req.is_incognito or chat_req.mode == "incognito"
    print(f"📥 [REQUEST] Mode: {chat_req.mode} | User: {chat_req.user_id} | Msg: {chat_req.message[:50]}... {'🕵️ [INCOGNITO]' if effective_incognito else ''}")
    accumulated = []
    client_ip = get_client_ip(request)
    identity = _require_identity(request, chat_req.user_id, chat_req.user_name)
    usage_request_id, account_snapshot = _claim_metered_hit(identity, "/chat/stream")
    started_at = runtime_metrics.start_request("/chat/stream", chat_req.mode)
    effective_user_id = identity.user_id
    effective_user_name = identity.user_name
    effective_user_email = identity.user_email

    async def event_generator():
        ok = False
        error_message = ""
        try:
            yield _account_event_payload(account_snapshot)
            if chat_req.image_data:
                is_founder = identity.is_founder
                saw_failure_payload = False
                async for chunk in analyze_image_stream(
                    image_data=chat_req.image_data,
                    user_question=chat_req.message,
                    conversation_history=chat_req.history,
                    is_founder=is_founder
                ):
                    token = _extract_persistable_payload(chunk)
                    if token:
                        accumulated.append(token)
                        if _payload_indicates_failed_run(token):
                            saw_failure_payload = True
                    yield chunk

                full_response = "".join(accumulated).replace('\\n', '\n')
                if not effective_incognito:
                    loop = asyncio.get_running_loop()
                    loop.run_in_executor(
                        None,
                        save_to_firebase_bg,
                        chat_req.message,
                        full_response,
                        "VISION",
                        effective_user_id,
                        effective_user_email,
                        client_ip,
                        chat_req.location,
                        "vision",
                        chat_req.mode,
                    )
                ok = not saw_failure_payload
                _finalize_metered_hit(
                    identity,
                    usage_request_id,
                    ok=ok,
                    error_message="" if ok else "Vision request returned an error payload.",
                )
                return

            async for chunk in stream_altair_response(
                chat_req.message,
                chat_req.history,
                user_id=effective_user_id,
                user_email=effective_user_email,
                user_name=effective_user_name,
                mode=chat_req.mode,
                use_openrouter=effective_use_openrouter,
                deep_search=chat_req.deep_search,
                location=chat_req.location,
                auth_verified=identity.is_authenticated
            ):
                token = _extract_persistable_payload(chunk)
                if token:
                    accumulated.append(token)
                yield chunk

            full_response = "".join(accumulated).replace('\\n', '\n')
            if not effective_incognito:
                loop = asyncio.get_running_loop()
                loop.run_in_executor(
                    None,
                    save_to_firebase_bg,
                    chat_req.message,
                    full_response,
                    "STREAMED",
                    effective_user_id,
                    effective_user_email,
                    client_ip,
                    chat_req.location,
                        "pro" if effective_use_openrouter else "lite",
                        chat_req.mode,
                    )
            _finalize_metered_hit(identity, usage_request_id, ok=True)
            ok = True
        except Exception as exc:
            import traceback
            traceback.print_exc()
            error_message = str(exc)
            status_code, message = _provider_error_message(exc)
            try:
                refunded_snapshot = _finalize_metered_hit(identity, usage_request_id, ok=False, error_message=error_message)
                yield _account_event_payload(refunded_snapshot)
            except Exception as release_exc:
                print(f"⚠️ Failed to finalize metered hit for {identity.user_id}: {release_exc}")
            print(f"⚠️ Stream error ({status_code}): {exc}")
            yield "data: " + message.replace("\n", "\\n") + "\n\n"
            yield "data: [DONE]\n\n"
        finally:
            runtime_metrics.finish_request("/chat/stream", started_at, ok=ok)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Nginx buffering disable
            **_build_charge_headers(account_snapshot),
        }
    )



# Legacy non-streaming endpoint (fallback)
@app.post("/chat")
async def chat(request: Request, payload: ChatRequest):
    _validate_chat_request(payload)
    identity = _require_identity(request, payload.user_id, payload.user_name)
    usage_request_id, account_snapshot = _claim_metered_hit(identity, "/chat")
    started_at = runtime_metrics.start_request("/chat", payload.mode)
    full_text = ""
    ok = False
    error_message = ""
    try:
        client_ip = get_client_ip(request)
        effective_use_openrouter = payload.use_openrouter or payload.mode == "uncensored"
        effective_incognito = payload.is_incognito or payload.mode == "incognito"
        effective_user_id = identity.user_id
        effective_user_name = identity.user_name
        effective_user_email = identity.user_email
        if payload.image_data:
            saw_failure_payload = False
            async for chunk in analyze_image_stream(
                image_data=payload.image_data,
                user_question=payload.message,
                conversation_history=payload.history,
                is_founder=identity.is_founder,
            ):
                persisted_chunk = _extract_persistable_payload(chunk)
                if persisted_chunk:
                    full_text += persisted_chunk.replace('\\n', '\n')
                    if _payload_indicates_failed_run(persisted_chunk):
                        saw_failure_payload = True
            ok = not saw_failure_payload
        else:
            async for chunk in stream_altair_response(
                payload.message,
                payload.history,
                effective_user_id,
                user_email=effective_user_email,
                user_name=effective_user_name,
                mode=payload.mode,
                use_openrouter=effective_use_openrouter,
                deep_search=payload.deep_search,
                location=payload.location,
                auth_verified=identity.is_authenticated
            ):
                persisted_chunk = _extract_persistable_payload(chunk)
                if persisted_chunk:
                    full_text += persisted_chunk.replace('\\n', '\n')
            ok = True

        if not effective_incognito:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, save_to_firebase_bg, payload.message, full_text, "CHAT", effective_user_id,
                                 effective_user_email, client_ip, payload.location, "pro" if effective_use_openrouter else "lite", payload.mode)
        final_snapshot = _finalize_metered_hit(
            identity,
            usage_request_id,
            ok=ok,
            error_message="" if ok else "Vision request returned an error payload.",
        )
        runtime_metrics.finish_request("/chat", started_at, ok=ok)
        return {"response": full_text, "intent": "CHAT", "account": final_snapshot}
    except Exception as e:
        error_message = str(e)
        try:
            final_snapshot = _finalize_metered_hit(identity, usage_request_id, ok=False, error_message=error_message)
        except Exception as release_exc:
            final_snapshot = account_snapshot
            print(f"⚠️ Failed to finalize metered hit for {identity.user_id}: {release_exc}")
        runtime_metrics.finish_request("/chat", started_at, ok=False)
        status_code, detail = _provider_error_message(e)
        print(f"⚠️ /chat error ({status_code}): {e}")
        raise HTTPException(status_code=status_code, detail={"message": detail, "account": final_snapshot})


@app.get("/auth/firebase-config")
async def auth_firebase_config(request: Request):
    return {
        "provider": "firebase",
        "founder_email": FOUNDER_EMAIL,
        "firebase": get_firebase_public_config(),
        "default_login_credits": DEFAULT_LOGIN_CREDITS,
    }


@app.get("/auth/me")
async def auth_me(request: Request):
    identity = _require_identity(request)
    account = _ensure_account_for_identity(identity)
    return {
        "authenticated": True,
        "provider": identity.provider,
        "founder_email": FOUNDER_EMAIL,
        "firebase": get_firebase_public_config(),
        "user": {
            "user_id": identity.user_id,
            "email": identity.user_email,
            "name": identity.user_name,
            "is_founder": identity.is_founder,
        },
        "account": account,
    }


@app.post("/payments/razorpay/order")
async def razorpay_order(request: Request, payload: RazorpayOrderRequest):
    identity = _require_identity(request, payload.user_id)
    placeholder = create_razorpay_placeholder_order(
        user_id=identity.user_id,
        email=identity.user_email,
        display_name=identity.user_name,
        plan_code=payload.plan_code,
        credits_pack=payload.credits_pack,
        amount_paise=payload.amount_paise,
    )
    return {
        "provider": "razorpay",
        "configured": False,
        "message": "Razorpay keys abhi configured nahi hain. Placeholder order backend mein create ho gaya hai.",
        **placeholder,
    }




_start_time = time.time()

@app.get("/health")
async def health():
    uptime_s = int(time.time() - _start_time)
    h, m, s = uptime_s // 3600, (uptime_s % 3600) // 60, uptime_s % 60
    runtime_snapshot = runtime_metrics.snapshot()
    memory_stats = await asyncio.to_thread(get_memory_stats)
    return {
        "status":  "online",
        "engine":  "TIFLO AI",
        "version": "3.1-runtime-upgrade",
        "model":   "llama-3.3-70b-versatile",
        "vision":  "llama-4-scout-17b",
        "uptime":  f"{h:02d}:{m:02d}:{s:02d}",
        "features": [
            "streaming",
            "web_search",
            "agents",
            "rag",
            "vision",
            "url_analysis",
            "firebase_auth",
            "credit_limits",
            "caching",
            "runtime_metrics",
            "ui_generator",
            "cold_outreach",
            "aso_launch_kit",
        ],
        "auth_provider": "firebase",
        "active_requests": runtime_snapshot.get("active_requests", 0),
        "firebase_ready": memory_stats.get("firebase_ready", False),
        "cache_sizes": {
            "router": router_cache.snapshot().get("size", 0),
            "summary": summary_cache.snapshot().get("size", 0),
            "search": search_cache.snapshot().get("size", 0),
            "followups": followup_cache.snapshot().get("size", 0),
        }
    }


@app.post("/analyze/url")
async def analyze_url_endpoint(request: Request, payload: UrlAnalysisRequest):
    identity = _require_identity(request, payload.user_id)
    usage_request_id, account_snapshot = _claim_metered_hit(identity, "/analyze/url")
    started_at = runtime_metrics.start_request("/analyze/url", "url_analysis")
    raw_input = (payload.url or "").strip()
    urls = extract_urls(raw_input)
    if not urls and raw_input.startswith(("http://", "https://")):
        urls = [raw_input]
    if not urls:
        _finalize_metered_hit(identity, usage_request_id, ok=False, error_message="Invalid URL payload.")
        runtime_metrics.finish_request("/analyze/url", started_at, ok=False)
        raise HTTPException(status_code=400, detail="A valid public URL is required.")

    async def stream():
        ok = False
        error_message = ""
        try:
            yield _account_event_payload(account_snapshot)
            if len(urls) == 1:
                saw_failure_payload = False
                async for chunk in analyze_url_stream(urls[0], payload.question):
                    persisted_chunk = _extract_persistable_payload(chunk)
                    if persisted_chunk and _payload_indicates_failed_run(persisted_chunk):
                        saw_failure_payload = True
                    yield chunk
                ok = not saw_failure_payload
            else:
                yield "data: __STATUS__:🔗 Analyzing links...\n\n"
                combined = await analyze_multiple_urls(urls, payload.question)
                yield "data: " + combined.replace("\n", "\\n") + "\n\n"
                yield "data: [DONE]\n\n"
                ok = True
            _finalize_metered_hit(
                identity,
                usage_request_id,
                ok=ok,
                error_message="" if ok else "URL analysis returned an error payload.",
            )
        except Exception as exc:
            error_message = str(exc)
            status_code, message = _provider_error_message(exc)
            try:
                refunded_snapshot = _finalize_metered_hit(identity, usage_request_id, ok=False, error_message=error_message)
                yield _account_event_payload(refunded_snapshot)
            except Exception as release_exc:
                print(f"⚠️ Failed to finalize metered URL hit for {identity.user_id}: {release_exc}")
            print(f"⚠️ URL analysis error ({status_code}): {exc}")
            yield "data: " + message.replace("\n", "\\n") + "\n\n"
            yield "data: [DONE]\n\n"
        finally:
            runtime_metrics.finish_request("/analyze/url", started_at, ok=ok)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", **_build_charge_headers(account_snapshot)},
    )


@app.post("/analyze/image")
async def analyze_image_upload(
    request: Request,
    file: UploadFile = File(...),
    question: str = Form(default=""),
    user_id: str = Form(default="guest")
):
    """
    Multipart image upload endpoint.
    Frontend can POST an actual image file here.
    """
    identity = _require_identity(request, user_id)
    usage_request_id, account_snapshot = _claim_metered_hit(identity, "/analyze/image")
    started_at = runtime_metrics.start_request("/analyze/image", "vision")
    try:
        guessed_type = mimetypes.guess_type(file.filename or "")[0] if file.filename else None
        content_type = (file.content_type or guessed_type or "application/octet-stream").lower()
        supported = {
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
            "image/heic",
            "image/heif",
            "image/bmp",
            "image/tiff",
            "application/pdf",
            "text/plain",
            "video/mp4",
            "video/quicktime",
            "video/webm",
        }

        if content_type not in supported:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported type '{content_type}'. "
                    "Use JPG/PNG/GIF/WEBP/HEIC/BMP/TIFF, PDF, TXT, or MP4/MOV/WebM."
                ),
            )

        raw_bytes = await file.read()
        if len(raw_bytes) > 20 * 1024 * 1024:  # 20MB cap
            raise HTTPException(status_code=413, detail="Image too large. Max 20MB.")

        data_uri = encode_file_to_base64(raw_bytes, content_type)
        is_founder = identity.is_founder

        async def stream():
            ok = False
            error_message = ""
            try:
                yield _account_event_payload(account_snapshot)
                saw_failure_payload = False
                async for chunk in analyze_image_stream(
                    image_data=data_uri,
                    user_question=question or "Analyze this image in detail.",
                    conversation_history=[],
                    is_founder=is_founder
                ):
                    persisted_chunk = _extract_persistable_payload(chunk)
                    if persisted_chunk and _payload_indicates_failed_run(persisted_chunk):
                        saw_failure_payload = True
                    yield chunk
                ok = not saw_failure_payload
                _finalize_metered_hit(
                    identity,
                    usage_request_id,
                    ok=ok,
                    error_message="" if ok else "Image analysis returned an error payload.",
                )
            except Exception as exc:
                error_message = str(exc)
                status_code, message = _provider_error_message(exc)
                try:
                    refunded_snapshot = _finalize_metered_hit(identity, usage_request_id, ok=False, error_message=error_message)
                    yield _account_event_payload(refunded_snapshot)
                except Exception as release_exc:
                    print(f"⚠️ Failed to finalize metered image hit for {identity.user_id}: {release_exc}")
                print(f"⚠️ Image analysis stream error ({status_code}): {exc}")
                yield "data: " + message.replace("\n", "\\n") + "\n\n"
                yield "data: [DONE]\n\n"
            finally:
                runtime_metrics.finish_request("/analyze/image", started_at, ok=ok)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", **_build_charge_headers(account_snapshot)}
        )
    except Exception as exc:
        try:
            _finalize_metered_hit(identity, usage_request_id, ok=False, error_message=str(exc))
        except Exception as release_exc:
            print(f"⚠️ Failed to finalize metered image hit for {identity.user_id}: {release_exc}")
        runtime_metrics.finish_request("/analyze/image", started_at, ok=False)
        raise


class MemoryExtractRequest(BaseModel):
    user_message: str
    ai_response: str
    current_profile: dict = Field(default_factory=dict)
    current_facts: list = Field(default_factory=list)

@app.post("/memory/extract")
async def extract_memory(request: Request, payload: MemoryExtractRequest):
    import json
    from groq import Groq
    
    groq_api_key = os.getenv("GROQ_API_KEY")
    client = Groq(api_key=groq_api_key)
    
    system_prompt = """You are a highly precise user-fact extractor. Output ONLY a valid JSON object.
Analyze the latest user message and AI response, extract key personal facts or preferences about the user, and merge/update them with the current profile and facts list.

RULES:
- Clean up duplicate or contradictory facts.
- Do not extract speculative facts. Only extract definite personal details (e.g. name, role, background, interests, key milestones).
- Keep the JSON format EXACTLY like:
{
  "user_profile": {"name": "...", "role": "...", "background": "...", "interests": "..."},
  "key_facts": ["fact 1", "fact 2"]
}
"""
    user_prompt = f"""Current Profile: {json.dumps(payload.current_profile)}
Current Facts: {json.dumps(payload.current_facts)}

Latest Turn:
User: {payload.user_message}
AI: {payload.ai_response}
"""
    try:
        runtime_metrics.record_provider("groq")
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content.strip())
        print(f"🧠 [LOCAL MEMORY EXTRACT] Profile: {result.get('user_profile')}")
        return result
    except Exception as e:
        print(f"⚠️ Memory extraction error: {e}")
        return {"user_profile": payload.current_profile, "key_facts": payload.current_facts}


@app.get("/stats")
async def stats():
    runtime_snapshot = runtime_metrics.snapshot()
    memory_stats = await asyncio.to_thread(get_memory_stats)
    return {
        "engine":      "TIFLO AI v3.1",
        "providers":   ["Groq Cloud", "OpenRouter"],
        "models": {
            "chat": "llama-3.3-70b-versatile",
            "router": "llama-3.1-8b-instant",
            "vision": "meta-llama/llama-4-scout-17b-16e-instruct",
            "uncensored": "gryphe/mythomax-l2-13b",
        },
        "capabilities": {
            "streaming":   True,
            "web_search":  True,
            "agents":      True,
            "rag":         True,
            "code_runner": False,
            "multi_step_agents": True,
            "runtime_metrics": True,
            "ttl_caching": True,
            "url_analysis": True,
            "firebase_auth": True,
            "credit_limits": True,
            "razorpay_placeholder": True,
            "ui_generator": True,
            "cold_outreach": True,
            "aso_launch_kit": True,
        },
        "uptime_seconds": int(time.time() - _start_time),
        "memory": memory_stats,
        "runtime": runtime_snapshot,
        "caches": {
            "router": router_cache.snapshot(),
            "summary": summary_cache.snapshot(),
            "search": search_cache.snapshot(),
            "followups": followup_cache.snapshot(),
        },
    }


@app.post("/voice/transcribe")
async def voice_transcribe(request: Request, file: UploadFile = File(...)):
    """
    Receives raw wav audio from browser Web Audio API and transcribes it in real-time
    using Groq's lightning-fast Whisper Large V3 engine.
    """
    try:
        contents = await file.read()
        if len(contents) > 12 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Audio too large. Max 12MB.")
        print(f"🎙️ Voice Engine: Received {len(contents)} bytes of audio. Forwarding to Groq Whisper...")
        
        # Call Groq audio transcription
        runtime_metrics.record_provider("groq")
        transcription = groq_client.audio.transcriptions.create(
            file=(file.filename, contents),
            model="whisper-large-v3",
            response_format="verbose_json"
        )
        print(f"🎙️ Voice Engine: Transcription success -> '{transcription.text}'")
        return {"text": transcription.text}
    except Exception as e:
        print(f"⚠️ Voice Engine Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/feedback")
async def chat_feedback(request: Request, req: FeedbackRequest):
    print(f"📥 [FEEDBACK] Type: {req.feedback_type} | User: {req.user_id} | Text: {req.feedback_text[:50]}...")
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, save_feedback_to_firebase_bg, 
        req.user_id, req.chat_id, req.feedback_type, req.feedback_text, req.last_user_message, req.last_ai_message)
    return {"status": "success", "message": "Feedback submitted successfully"}


@app.post("/chat/share")
async def chat_share(request: Request, req: ShareChatRequest):
    print(f"📥 [SHARE CHAT] Creating public link for '{req.title}' ({len(req.messages)} msgs)...")
    try:
        shared_id = save_shared_chat(req.messages, req.title)
        return {"status": "success", "shared_id": shared_id}
    except Exception as e:
        print(f"⚠️ Share Chat Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/share/{shared_id}")
async def chat_share_get(request: Request, shared_id: str):
    print(f"📤 [SHARE CHAT] Fetching public link '{shared_id}'...")
    try:
        chat_data = get_shared_chat(shared_id)
        if not chat_data:
            raise HTTPException(status_code=404, detail="Shared chat not found")
        return {"status": "success", "chat": chat_data}
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"⚠️ Fetch Shared Chat Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/admin/chats")
async def admin_chats_get(request: Request):
    identity = _require_identity(request)
    if not identity.is_founder:
        raise HTTPException(status_code=403, detail="Forbidden: founder access only.")

    print(f"🔑 [ADMIN] Secure fetching all conversation records for {identity.user_id}...")
    try:
        chats_data = get_all_chats()
        return {"status": "success", "chats": chats_data}
    except Exception as e:
        print(f"⚠️ Admin Chat Fetch Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))




if __name__ == "__main__":
    import uvicorn
    import os
    # Hugging Face Spaces default port is 7860, local default is 8001
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
