"""
image_analyzer.py — Tiflo AI Vision Engine & Multi-Modal Parser
=============================================================
Supports: base64 images, non-standard formats (HEIC, BMP, TIFF),
video keyframe frame extraction (MP4, MOV, WebM), PDF text extraction, 
and raw text files. Uses llama-4-scout and llama-3.3-70b via Groq.
"""

import os
import re
import base64
import time
import io
import tempfile
import asyncio
import cv2
from PIL import Image
import pillow_heif
from pypdf import PdfReader
try:
    import fitz
    PYMUPDF_AVAILABLE = True
    print("✅ PyMuPDF (fitz) loaded successfully for PDF extraction")
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("⚠️ PyMuPDF not found. Falling back to pypdf.")
from groq import Groq
from dotenv import load_dotenv
from typing import AsyncGenerator
from groq import BadRequestError
from runtime_state import runtime_metrics

# Register HEIF/HEIC support for PIL
pillow_heif.register_heif_opener()

load_dotenv()
_groq = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Models
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
TEXT_MODEL = "llama-3.3-70b-versatile"



def _format_recent_vision_history(conversation_history: list | None, limit: int = 3) -> str:
    if not conversation_history:
        return ""

    lines = []
    for msg in conversation_history[-limit:]:
        role = str(msg.get("role", "user")).strip().lower()
        content = str(msg.get("content", "")).strip()
        if not content:
            continue
        label = "User" if role == "user" else "Assistant"
        lines.append(f"{label}: {content[:500]}")
    return "\n".join(lines)



def _question_prefers_extraction(question: str) -> bool:
    lower = (question or "").lower()
    hints = [
        "extract",
        "ocr",
        "text",
        "table",
        "data",
        "numbers",
        "price",
        "pricing",
        "invoice",
        "receipt",
        "document",
        "website",
        "screen",
        "screenshot",
        "read",
        "what does this say",
    ]
    return any(hint in lower for hint in hints)



def _build_multimodal_user_prompt(
    user_question: str,
    conversation_history: list | None,
    media_kind: str,
) -> str:
    question = (user_question or "").strip()
    if not question:
        question = f"Analyze this {media_kind} in detail."

    extraction_bias = _question_prefers_extraction(question)
    history_block = _format_recent_vision_history(conversation_history)
    history_text = f"\n\nRECENT CONTEXT:\n{history_block}" if history_block else ""

    focus = (
        "Prioritize exact extraction of visible text, numbers, labels, tables, UI sections, and any structured data."
        if extraction_bias
        else "Prioritize the direct answer first, then the most useful visual evidence."
    )

    return (
        f"USER REQUEST: {question}{history_text}\n\n"
        f"MEDIA TYPE: {media_kind}\n"
        f"TASK PRIORITY: {focus}\n\n"
        "RULES:\n"
        "- Answer directly from what is visible.\n"
        "- If this is a screenshot or webpage image, identify the main sections, visible text, and key actions/CTAs.\n"
        "- If this contains tables/charts, extract the numbers faithfully.\n"
        "- If text is visible, include an **Extracted Text** section with the important lines.\n"
        "- Distinguish direct observation from inference.\n"
        "- Keep it sharp, structured, and useful."
    )



async def _stream_openrouter_multimodal(messages: list, model: str, temperature: float = 0.2):
    or_key = os.getenv("OPENROUTER_API_KEY")
    if not or_key:
        raise RuntimeError("OPENROUTER_API_KEY missing")

    headers = {
        "Authorization": f"Bearer {or_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://tiflo.in",
        "X-Title": "Tiflo AI",
    }
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": temperature,
    }

    import aiohttp
    import json

    runtime_metrics.record_provider("openrouter")
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        ) as resp:
            if resp.status != 200:
                err_text = await resp.text()
                raise RuntimeError(f"OpenRouter Vision Error {resp.status}: {err_text[:200]}")

            async for line in resp.content:
                if not line:
                    continue
                decoded_line = line.decode("utf-8", errors="ignore").strip()
                if not decoded_line.startswith("data: "):
                    continue
                data_str = decoded_line[6:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    data_json = json.loads(data_str)
                    token = data_json["choices"][0]["delta"].get("content", "")
                except Exception:
                    token = ""
                if token:
                    yield token



async def _stream_groq_multimodal(messages: list, model: str, temperature: float = 0.2):
    runtime_metrics.record_provider("groq")
    try:
        stream = _groq.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=1600,
            stream=True,
        )
    except BadRequestError as exc:
        raise RuntimeError(f"Groq vision request rejected: {exc}") from exc

    for chunk in stream:
        token = chunk.choices[0].delta.content or ""
        if token:
            yield token



async def _stream_best_multimodal(messages: list, preferred_kind: str):
    errors = []
    openrouter_model = "meta-llama/llama-3.2-11b-vision-instruct"

    if os.getenv("OPENROUTER_API_KEY"):
        try:
            async for token in _stream_openrouter_multimodal(messages, model=openrouter_model, temperature=0.2):
                yield token
            return
        except Exception as exc:
            errors.append(str(exc))
            print(f"⚠️ OpenRouter multimodal fallback triggered: {exc}")

    try:
        async for token in _stream_groq_multimodal(messages, model=VISION_MODEL, temperature=0.2):
            yield token
        return
    except Exception as exc:
        errors.append(str(exc))
        print(f"⚠️ Groq multimodal fallback failed: {exc}")

    combined = "; ".join(errors) if errors else "No multimodal provider is configured"
    raise RuntimeError(f"{preferred_kind.title()} analysis unavailable: {combined}")


def preprocess_image_data(data_uri: str) -> tuple[bool, str, str]:
    """
    If the image format is non-standard (HEIC, BMP, TIFF, ICO, etc.),
    convert it to standard JPEG using PIL / pillow-heif and return the standard data_uri.
    Returns: (success, mime_type, final_data_uri)
    """
    if not data_uri.startswith("data:"):
        return True, "image/jpeg", data_uri
        
    pattern = r'^data:([^;]+);base64,(.+)$'
    match = re.match(pattern, data_uri)
    if not match:
        return False, "", data_uri
        
    mime_type = match.group(1).lower()
    b64_data = match.group(2)
    
    # Standard format supported by Groq
    if mime_type in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
        return True, mime_type, data_uri
        
    try:
        raw_bytes = base64.b64decode(b64_data)
        image = Image.open(io.BytesIO(raw_bytes))
        
        # Convert RGBA/P modes to RGB for JPEG
        if image.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "RGBA":
                background.paste(image, mask=image.split()[3]) # alpha channel mask
            else:
                background.paste(image)
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")
            
        out_buf = io.BytesIO()
        image.save(out_buf, format="JPEG", quality=85)
        converted_b64 = base64.b64encode(out_buf.getvalue()).decode('utf-8')
        
        new_uri = f"data:image/jpeg;base64,{converted_b64}"
        print(f"🔄 Converted non-standard image type '{mime_type}' to image/jpeg")
        return True, "image/jpeg", new_uri
    except Exception as e:
        print(f"⚠️ Failed to convert image '{mime_type}': {e}")
        return False, mime_type, data_uri


def extract_video_keyframes(b64_data: str, num_keyframes: int = 4) -> list[str]:
    """
    Decodes the video base64, saves to a temp file, extracts evenly-spaced keyframes,
    resizes them for speed, encodes as JPEG base64, and returns them.
    """
    try:
        raw_bytes = base64.b64decode(b64_data)
    except Exception as e:
        print(f"⚠️ Failed to decode base64 video bytes: {e}")
        return []
        
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, f"temp_video_{int(time.time())}.mp4")
    
    try:
        with open(temp_file_path, "wb") as f:
            f.write(raw_bytes)
    except Exception as e:
        print(f"⚠️ Failed to write temp video file: {e}")
        return []
        
    keyframes_base64 = []
    try:
        cap = cv2.VideoCapture(temp_file_path)
        if not cap.isOpened():
            print("⚠️ Failed to open video file using OpenCV")
            return []
            
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            print("⚠️ Video has invalid frame count")
            return []
            
        # Distribute frames: e.g. at 10%, 40%, 70%, 90%
        pcts = [0.1, 0.4, 0.7, 0.9]
        frame_indices = [int(total_frames * p) for p in pcts]
        
        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                # Keep payload small and fast
                h, w = frame.shape[:2]
                max_dim = 640
                if max(h, w) > max_dim:
                    scale = max_dim / max(h, w)
                    frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
                    
                success, buffer = cv2.imencode(".jpg", frame)
                if success:
                    b64_frame = base64.b64encode(buffer).decode('utf-8')
                    keyframes_base64.append(f"data:image/jpeg;base64,{b64_frame}")
                    
        cap.release()
    except Exception as e:
        print(f"⚠️ Error during keyframe extraction: {e}")
    finally:
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass
                
    return keyframes_base64


def extract_pdf_text(b64_data: str) -> str:
    """
    Decodes the PDF base64 and extracts text from all pages using PyMuPDF (fitz) or pypdf fallback.
    """
    try:
        raw_bytes = base64.b64decode(b64_data)
        text_parts = []
        
        if PYMUPDF_AVAILABLE:
            print("📄 PyMuPDF (fitz) Engine: Extracting PDF text...")
            doc = fitz.open(stream=io.BytesIO(raw_bytes), filetype="pdf")
            for i, page in enumerate(doc):
                text = page.get_text()
                if text:
                    text_parts.append(f"--- PAGE {i+1} ---\n{text}")
        else:
            print("📄 pypdf Engine: Extracting PDF text...")
            reader = PdfReader(io.BytesIO(raw_bytes))
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    text_parts.append(f"--- PAGE {i+1} ---\n{text}")
                    
        return "\n\n".join(text_parts)[:15000] # Cap to 15k chars for prompt safety
    except Exception as e:
        print(f"⚠️ Failed to extract text from PDF: {e}")
        return f"Error parsing PDF file: {e}"


async def analyze_image_stream(
    image_data: str,
    user_question: str = "",
    conversation_history: list = None,
    is_founder: bool = False
) -> AsyncGenerator[str, None]:
    """
    Unified stream engine to analyze images, videos, text files, and PDFs.
    """
    start = time.time()
    persona = "TIFLO AI — your founder's trusted vision engine" if is_founder else "TIFLO AI"

    # 1. Check if public URL or base64 Data URI
    if not image_data.startswith("data:"):
        # Public image URL path
        mime_type = "image/jpeg"
        is_video = False
        is_pdf = False
        is_text = False
        final_uri = image_data
    else:
        # Data URI path
        pattern = r'^data:([^;]+);base64,(.+)$'
        match = re.match(pattern, image_data)
        if not match:
            yield "data: ⚠️ Invalid attachment file format.\n\n"
            yield "data: [DONE]\n\n"
            return
            
        mime_type = match.group(1).lower()
        b64_data = match.group(2)
        
        is_video = mime_type.startswith("video/")
        is_pdf = mime_type == "application/pdf"
        is_text = mime_type.startswith("text/")
        
        final_uri = image_data

    # 2. Routing logic
    # ── CASE A: Video ──────────────────────────────────────────────────────────
    if is_video:
        yield "data: ⚙️ Extracting video frames...\n\n"
        keyframes = await asyncio.to_thread(extract_video_keyframes, b64_data)
        if not keyframes:
            yield "data: ⚠️ Failed to extract keyframes from the video. Please verify the video format.\n\n"
            yield "data: [DONE]\n\n"
            return
            
        yield f"data: ⚙️ Analyzing {len(keyframes)} video scenes...\n\n"
        
        user_prompt_text = _build_multimodal_user_prompt(
            user_question or "Describe this video with scene progression, visible text, and key details.",
            conversation_history,
            media_kind="video",
        )

        image_contents = [{"type": "image_url", "image_url": {"url": kf}} for kf in keyframes]
        messages = [
            {
                "role": "system",
                "content": f"You are {persona}, a cutting-edge multimodal intelligence. You analyze video frame sequences with high precision.",
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt_text},
                    *image_contents,
                ],
            },
        ]

        try:
            async for token in _stream_best_multimodal(messages, preferred_kind="video"):
                yield "data: " + token.replace('\n', '\\n') + "\n\n"
            print(f"✅ Video analyzed in {round(time.time() - start, 2)}s via multimodal provider chain")
        except Exception as e:
            yield f"data: ⚠️ Video analysis failed: {str(e)[:140]}\n\n"

        yield "data: [DONE]\n\n"
        return

    # ── CASE B: PDF Document ──────────────────────────────────────────────────
    elif is_pdf:
        yield "data: ⚙️ Parsing PDF text...\n\n"
        pdf_text = await asyncio.to_thread(extract_pdf_text, b64_data)
        if not pdf_text.strip():
            yield "data: ⚠️ PDF parsed but no text was extracted.\n\n"
            yield "data: [DONE]\n\n"
            return
            
        yield "data: ⚙️ Analyzing document...\n\n"
        
        system_content = f"""You are {persona}, an elite analyst. 
Analyze the provided document context carefully and answer the user's questions with absolute accuracy.
Structure your findings beautifully with bullet points and bold terms.
"""
        user_prompt_text = f"""USER QUESTION: {user_question or 'Summarize this PDF document.'}

=== PDF CONTENT ===
{pdf_text}
"""
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt_text}
        ]
        
        try:
            runtime_metrics.record_provider("groq")
            stream = _groq.chat.completions.create(
                model=TEXT_MODEL,
                messages=messages,
                temperature=0.3,
                max_tokens=1500,
                stream=True
            )
            for chunk in stream:
                token = chunk.choices[0].delta.content or ""
                if token:
                    yield "data: " + token.replace('\n', '\\n') + "\n\n"
            print(f"✅ PDF analyzed in {round(time.time() - start, 2)}s")
        except Exception as e:
            yield f"data: ⚠️ PDF analysis failed: {str(e)[:100]}\n\n"
            
        yield "data: [DONE]\n\n"
        return

    # ── CASE C: Text File ─────────────────────────────────────────────────────
    elif is_text:
        yield "data: ⚙️ Reading text file...\n\n"
        try:
            raw_text = base64.b64decode(b64_data).decode('utf-8', errors='ignore')
        except Exception as e:
            yield f"data: ⚠️ Failed to decode text file: {str(e)}\n\n"
            yield "data: [DONE]\n\n"
            return
            
        yield "data: ⚙️ Analyzing text content...\n\n"
        system_content = f"You are {persona}, a highly advanced text analytics engine."
        user_prompt_text = f"""USER QUESTION: {user_question or 'Summarize this text file.'}

=== FILE CONTENT ===
{raw_text[:15000]}
"""
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt_text}
        ]
        
        try:
            runtime_metrics.record_provider("groq")
            stream = _groq.chat.completions.create(
                model=TEXT_MODEL,
                messages=messages,
                temperature=0.3,
                max_tokens=1500,
                stream=True
            )
            for chunk in stream:
                token = chunk.choices[0].delta.content or ""
                if token:
                    yield "data: " + token.replace('\n', '\\n') + "\n\n"
            print(f"✅ Text file analyzed in {round(time.time() - start, 2)}s")
        except Exception as e:
            yield f"data: ⚠️ Text analysis failed: {str(e)[:100]}\n\n"
            
        yield "data: [DONE]\n\n"
        return

    # ── CASE D: Image ─────────────────────────────────────────────────────────
    else:
        # Standardize and preprocess image (including conversions of HEIC/BMP/TIFF)
        success, final_mime, final_uri = await asyncio.to_thread(preprocess_image_data, final_uri)
        if not success:
            yield f"data: ⚠️ Unsupported or corrupted image format. Please upload JPEG, PNG, WEBP, GIF, HEIC, or BMP.\n\n"
            yield "data: [DONE]\n\n"
            return
            
        image_content = {"type": "image_url", "image_url": {"url": final_uri}}
        if not user_question.strip():
            user_question = (
                "Analyze this image or screenshot in detail. "
                "Describe what matters, extract visible text, identify key UI/data elements, and give insights."
            )

        system_content = f"""You are {persona}, a powerful multimodal AI.
Analyze images with surgical precision.

FORMAT:
- Lead with the most important observation in **bold**.
- Use bullet points for multiple findings.
- If text is visible, include an **Extracted Text** section.
- If this is a screenshot or webpage image, identify the visible sections, labels, actions, and important data.
- Flag anything unusual, important, or worth noting.
- Match the user's language/vibe naturally.
"""
        messages = [
            {"role": "system", "content": system_content},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": _build_multimodal_user_prompt(user_question, conversation_history, media_kind="image/screenshot"),
                    },
                    image_content,
                ],
            },
        ]

        try:
            async for token in _stream_best_multimodal(messages, preferred_kind="image"):
                yield "data: " + token.replace('\n', '\\n') + "\n\n"
            print(f"✅ Image analyzed in {round(time.time() - start, 2)}s using multimodal provider chain")
        except Exception as e:
            yield f"data: ⚠️ Image analysis failed: {str(e)[:140]}\n\n"

        yield "data: [DONE]\n\n"


def encode_file_to_base64(file_bytes: bytes, mime_type: str) -> str:
    """Convert raw file bytes to base64 data URI."""
    b64 = base64.b64encode(file_bytes).decode('utf-8')
    return f"data:{mime_type};base64,{b64}"
