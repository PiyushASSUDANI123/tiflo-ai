"""
memory_db.py — Firebase SUSPENDED
All Firestore writes/reads are disabled. Functions return safe no-op defaults.
Re-enable by restoring the original implementation.
"""
import os
from dotenv import load_dotenv

load_dotenv()

FOUNDER_ID = os.getenv("FOUNDER_USER_ID", "")
FOUNDER_EMAIL = os.getenv("FOUNDER_EMAIL", "")
db = None  # Firebase suspended


def save_interaction(user_id, message, response, intent="CHIT_CHAT", user_email="", user_ip="", user_location="", model="lite", mode="default"):
    """Firebase suspended — no-op."""
    print(f"[Firebase SUSPENDED] save_interaction skipped for user: {user_id}")


def get_recent_context(user_id, limit=5):
    """Firebase suspended — returns empty context."""
    return ""


def add_to_knowledge(content, source="manual", doc_id: str = ""):
    """Firebase suspended — no-op."""
    print(f"[Firebase SUSPENDED] add_to_knowledge skipped")


def get_memory_stats() -> dict:
    """Firebase suspended — returns zeroed stats."""
    return {
        "knowledge_base": 0,
        "conversations": 0,
        "private_founder": 0,
        "firebase_ready": False,
        "suspended": True,
    }


def save_feedback(user_id, chat_id, feedback_type, feedback_text, last_user_msg, last_ai_msg):
    """Firebase suspended — no-op."""
    print(f"[Firebase SUSPENDED] save_feedback skipped for user: {user_id}")


def save_shared_chat(messages: list, title: str) -> str:
    """Firebase suspended — returns a placeholder ID."""
    print(f"[Firebase SUSPENDED] save_shared_chat skipped")
    return "firebase-suspended"


def get_shared_chat(shared_id: str) -> dict:
    """Firebase suspended — returns None."""
    print(f"[Firebase SUSPENDED] get_shared_chat skipped for id: {shared_id}")
    return None


def get_all_chats():
    """Firebase suspended — returns empty list."""
    return []
