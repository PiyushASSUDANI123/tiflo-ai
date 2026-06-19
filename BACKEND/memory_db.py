import os
import time
import json
from firebase_admin import firestore
from dotenv import load_dotenv
from datetime import datetime
from firebase_setup import FOUNDER_EMAIL, FOUNDER_USER_ID, get_firestore_client

load_dotenv()

# Founder Identity
FOUNDER_ID = FOUNDER_USER_ID
db = get_firestore_client()

def save_interaction(user_id, message, response, intent="CHIT_CHAT", user_email="", user_ip="", user_location="", model="lite", mode="default"):
    """Save detailed Q&A to Firestore with secure analytics."""
    if not db:
        return
    try:
        doc_ref = db.collection("chats").document()
        doc_ref.set({
            "user_id": str(user_id),
            "user_email": str(user_email)[:320] if user_email else "guest",
            "user_ip": str(user_ip) if user_ip else "unknown",
            "user_location": str(user_location) if user_location else "unknown",
            "user_message": str(message)[:20000],
            "ai_response": str(response)[:50000],
            "intent": str(intent),
            "model": str(model),
            "mode": str(mode),
            "timestamp": firestore.SERVER_TIMESTAMP
        })
        print(f"✅ Firebase saved detailed interaction [user: {user_id}]")
    except Exception as e:
        print(f"⚠️ Firebase save error: {e}")

def get_recent_context(user_id, limit=5):
    """Fetch last N messages for context."""
    if not db:
        return ""
    try:
        chats_ref = db.collection("chats")
        query = chats_ref.where("user_id", "==", str(user_id)).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit)
        results = query.stream()
        
        context_parts = []
        for doc in results:
            data = doc.to_dict()
            q = data.get("user_message", "")
            a = data.get("ai_response", "")
            context_parts.append(f"User: {q}\nAI: {a}")
            
        return "\n---\n".join(reversed(context_parts))
    except Exception as e:
        print(f"⚠️ Firebase fetch error: {e}")
        return ""

def add_to_knowledge(content, source="manual", doc_id: str = ""):
    """Store permanent knowledge in Firestore."""
    if not db:
        return
    try:
        doc_ref = db.collection("knowledge_base").document(str(doc_id).strip()) if doc_id else db.collection("knowledge_base").document()
        doc_ref.set({
            "content": str(content),
            "source": str(source),
            "added_at": firestore.SERVER_TIMESTAMP
        })
    except Exception as e:
        print(f"⚠️ Firebase KB error: {e}")


def get_memory_stats() -> dict:
    """Return high-level Firestore collection counts for operational scripts."""
    if not db:
        return {
            "knowledge_base": 0,
            "conversations": 0,
            "private_founder": 0,
            "firebase_ready": False,
        }

    try:
        knowledge_count = sum(1 for _ in db.collection("knowledge_base").limit(1000).stream())
        conversation_count = sum(1 for _ in db.collection("chats").limit(1000).stream())
        founder_count = sum(1 for _ in db.collection("chats").where("user_id", "==", FOUNDER_ID).limit(1000).stream())
        if founder_count == 0 and FOUNDER_EMAIL:
            founder_count = sum(
                1 for _ in db.collection("chats").where("user_email", "==", FOUNDER_EMAIL).limit(1000).stream()
            )
        return {
            "knowledge_base": knowledge_count,
            "conversations": conversation_count,
            "private_founder": founder_count,
            "firebase_ready": True,
        }
    except Exception as e:
        print(f"⚠️ Firebase stats error: {e}")
        return {
            "knowledge_base": 0,
            "conversations": 0,
            "private_founder": 0,
            "firebase_ready": False,
            "error": str(e),
        }

def save_feedback(user_id, chat_id, feedback_type, feedback_text, last_user_msg, last_ai_msg):
    """Store user feedback."""
    if not db:
        return
    try:
        doc_ref = db.collection("feedbacks").document()
        doc_ref.set({
            "user_id": str(user_id),
            "chat_id": str(chat_id),
            "feedback_type": str(feedback_type),
            "feedback_text": str(feedback_text),
            "last_user_message": str(last_user_msg),
            "last_ai_message": str(last_ai_msg),
            "timestamp": firestore.SERVER_TIMESTAMP
        })
    except Exception as e:
        print(f"⚠️ Firebase feedback save error: {e}")


def _sanitize_shared_messages(messages: list) -> list:
    sanitized = []
    for raw in messages[:100]:
        if not isinstance(raw, dict):
            continue

        role = str(raw.get("role", "assistant")).strip().lower()
        if role not in {"user", "assistant", "ai", "system"}:
            role = "assistant"

        image_data = ""
        raw_image = raw.get("image_data", "")
        if isinstance(raw_image, str):
            candidate = raw_image.strip()
            if (
                candidate.startswith("data:image/")
                or candidate.startswith("https://")
                or candidate.startswith("http://")
            ) and len(candidate) <= 250000:
                image_data = candidate

        sanitized.append({
            "role": role,
            "content": str(raw.get("content", ""))[:20000],
            "image_data": image_data,
        })
    return sanitized


def save_shared_chat(messages: list, title: str) -> str:
    """Save full chat history for public link sharing and return doc ID."""
    if not db:
        raise ValueError("Firebase is not initialized")
    try:
        doc_ref = db.collection("shared_chats").document()
        doc_ref.set({
            "title": str(title)[:200],
            "messages": _sanitize_shared_messages(messages),
            "shared_at": firestore.SERVER_TIMESTAMP
        })
        return doc_ref.id
    except Exception as e:
        print(f"⚠️ Firebase save shared chat error: {e}")
        raise e

def get_shared_chat(shared_id: str) -> dict:
    """Fetch shared chat history by unique ID."""
    if not db:
        raise ValueError("Firebase is not initialized")
    try:
        doc_ref = db.collection("shared_chats").document(str(shared_id))
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            # Convert timestamp to ISO string for API compatibility
            if "shared_at" in data and data["shared_at"]:
                data["shared_at"] = data["shared_at"].isoformat()
            return data
        return None
    except Exception as e:
        print(f"⚠️ Firebase fetch shared chat error: {e}")
        raise e


def get_all_chats():
    """Retrieve all chats from Firestore, sorted by timestamp descending, for admin dashboard."""
    if not db:
        return []
    try:
        chats_ref = db.collection("chats")
        query = chats_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(150)
        docs = query.stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            # Convert timestamp to ISO string for JSON serialization
            if "timestamp" in data and data["timestamp"]:
                try:
                    data["timestamp"] = data["timestamp"].isoformat()
                except Exception:
                    data["timestamp"] = str(data["timestamp"])
            else:
                data["timestamp"] = ""
            results.append(data)
        return results
    except Exception as e:
        print(f"⚠️ Error fetching all chats: {e}")
        return []
