import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from firebase_setup import DEFAULT_LOGIN_CREDITS, FOUNDER_EMAIL

DB_PATH = os.getenv("TIFLO_AUTH_DB_PATH", os.path.join(os.path.dirname(__file__), "tiflo_auth.sqlite3"))


class CreditManagerError(Exception):
    pass


class InsufficientCreditsError(CreditManagerError):
    pass


class ConcurrentHitError(CreditManagerError):
    pass


class UnknownUserError(CreditManagerError):
    pass


@dataclass
class UserSnapshot:
    user_id: str
    email: str
    display_name: str
    remaining_credits: int | None
    unlimited_access: bool
    active_hit_in_progress: bool
    used_credits: int
    total_hits: int
    created_at: str
    last_login_at: str
    last_seen_at: str
    default_login_credits: int = DEFAULT_LOGIN_CREDITS

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "display_name": self.display_name,
            "remaining_credits": self.remaining_credits,
            "unlimited_access": self.unlimited_access,
            "active_hit_in_progress": self.active_hit_in_progress,
            "used_credits": self.used_credits,
            "total_hits": self.total_hits,
            "created_at": self.created_at,
            "last_login_at": self.last_login_at,
            "last_seen_at": self.last_seen_at,
            "default_login_credits": self.default_login_credits,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def initialize_credit_store() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_accounts (
                user_id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                display_name TEXT NOT NULL DEFAULT '',
                credits INTEGER NOT NULL DEFAULT 25,
                used_credits INTEGER NOT NULL DEFAULT 0,
                total_hits INTEGER NOT NULL DEFAULT 0,
                unlimited_access INTEGER NOT NULL DEFAULT 0,
                active_hits INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                last_login_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usage_hits (
                request_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                route TEXT NOT NULL,
                status TEXT NOT NULL,
                deducted_credits INTEGER NOT NULL DEFAULT 0,
                refunded INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                finished_at TEXT,
                error_message TEXT DEFAULT '',
                FOREIGN KEY(user_id) REFERENCES user_accounts(user_id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_usage_hits_user_status ON usage_hits(user_id, status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_usage_hits_created_at ON usage_hits(created_at)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS razorpay_orders (
                order_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                plan_code TEXT NOT NULL,
                credits_pack INTEGER NOT NULL DEFAULT 0,
                amount_paise INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                notes TEXT DEFAULT '',
                FOREIGN KEY(user_id) REFERENCES user_accounts(user_id) ON DELETE CASCADE
            )
            """
        )


def _snapshot_from_row(row: sqlite3.Row) -> UserSnapshot:
    unlimited = bool(row["unlimited_access"])
    return UserSnapshot(
        user_id=str(row["user_id"]),
        email=str(row["email"]),
        display_name=str(row["display_name"]),
        remaining_credits=None if unlimited else int(row["credits"]),
        unlimited_access=unlimited,
        active_hit_in_progress=bool(row["active_hits"]),
        used_credits=int(row["used_credits"]),
        total_hits=int(row["total_hits"]),
        created_at=str(row["created_at"]),
        last_login_at=str(row["last_login_at"]),
        last_seen_at=str(row["last_seen_at"]),
    )


def _upsert_user_account_tx(conn: sqlite3.Connection, user_id: str, email: str, display_name: str) -> sqlite3.Row:
    normalized_email = _normalize_email(email)
    safe_name = (display_name or normalized_email.split("@")[0] or "User").strip()
    is_founder = normalized_email == FOUNDER_EMAIL
    now = _utc_now()

    row = conn.execute("SELECT * FROM user_accounts WHERE user_id = ?", (user_id,)).fetchone()
    if row:
        merged_email = normalized_email or row["email"]
        merged_name = safe_name or row["display_name"]
        unlimited_access = 1 if (bool(row["unlimited_access"]) or is_founder) else 0
        conn.execute(
            """
            UPDATE user_accounts
            SET email = ?, display_name = ?, unlimited_access = ?, last_login_at = ?, last_seen_at = ?
            WHERE user_id = ?
            """,
            (merged_email, merged_name, unlimited_access, now, now, user_id),
        )
    else:
        conn.execute(
            """
            INSERT INTO user_accounts (
                user_id, email, display_name, credits, used_credits, total_hits,
                unlimited_access, active_hits, created_at, last_login_at, last_seen_at
            )
            VALUES (?, ?, ?, ?, 0, 0, ?, 0, ?, ?, ?)
            """,
            (user_id, normalized_email, safe_name, DEFAULT_LOGIN_CREDITS, 1 if is_founder else 0, now, now, now),
        )

    updated = conn.execute("SELECT * FROM user_accounts WHERE user_id = ?", (user_id,)).fetchone()
    if not updated:
        raise UnknownUserError("User account could not be created.")
    return updated


def ensure_user_account(user_id: str, email: str, display_name: str = "") -> UserSnapshot:
    initialize_credit_store()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = _upsert_user_account_tx(conn, user_id, email, display_name)
        conn.execute("COMMIT")
        return _snapshot_from_row(row)


def get_user_snapshot(user_id: str) -> UserSnapshot:
    initialize_credit_store()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM user_accounts WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            raise UnknownUserError("User account not found.")
        return _snapshot_from_row(row)


def claim_hit(user_id: str, email: str, display_name: str, route: str) -> tuple[str, UserSnapshot]:
    initialize_credit_store()
    request_id = uuid.uuid4().hex
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = _upsert_user_account_tx(conn, user_id, email, display_name)

        active_hits = int(row["active_hits"])
        credits = int(row["credits"])
        unlimited_access = bool(row["unlimited_access"])
        used_credits = int(row["used_credits"])
        total_hits = int(row["total_hits"])
        now = _utc_now()

        if active_hits > 0:
            conn.execute("ROLLBACK")
            raise ConcurrentHitError("A request is already running for this user.")

        if not unlimited_access and credits <= 0:
            conn.execute("ROLLBACK")
            raise InsufficientCreditsError("No credits left for this user.")

        deducted = 0 if unlimited_access else 1
        next_credits = credits if unlimited_access else credits - 1

        conn.execute(
            """
            UPDATE user_accounts
            SET credits = ?, used_credits = ?, total_hits = ?, active_hits = 1, last_seen_at = ?
            WHERE user_id = ?
            """,
            (next_credits, used_credits + deducted, total_hits + 1, now, user_id),
        )
        conn.execute(
            """
            INSERT INTO usage_hits (
                request_id, user_id, route, status, deducted_credits, refunded,
                created_at, finished_at, error_message
            )
            VALUES (?, ?, ?, 'in_progress', ?, 0, ?, NULL, '')
            """,
            (request_id, user_id, route, deducted, now),
        )
        conn.execute("COMMIT")

    return request_id, get_user_snapshot(user_id)


def finish_hit(user_id: str, request_id: str, ok: bool, error_message: str = "") -> UserSnapshot:
    initialize_credit_store()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        account = conn.execute("SELECT * FROM user_accounts WHERE user_id = ?", (user_id,)).fetchone()
        hit = conn.execute("SELECT * FROM usage_hits WHERE request_id = ?", (request_id,)).fetchone()
        if not account or not hit:
            conn.execute("ROLLBACK")
            raise UnknownUserError("Hit session not found.")
        if str(hit["status"]) != "in_progress":
            conn.execute("ROLLBACK")
            return _snapshot_from_row(account)

        credits = int(account["credits"])
        used_credits = int(account["used_credits"])
        active_hits = max(0, int(account["active_hits"]) - 1)
        deducted_credits = int(hit["deducted_credits"])
        refunded = int(hit["refunded"])
        now = _utc_now()

        refund_credit = (not ok) and deducted_credits > 0 and not refunded
        next_credits = credits + 1 if refund_credit else credits
        next_used = max(0, used_credits - 1) if refund_credit else used_credits
        next_status = "completed" if ok else ("refunded" if refund_credit else "failed")

        conn.execute(
            """
            UPDATE user_accounts
            SET credits = ?, used_credits = ?, active_hits = ?, last_seen_at = ?
            WHERE user_id = ?
            """,
            (next_credits, next_used, active_hits, now, user_id),
        )
        conn.execute(
            """
            UPDATE usage_hits
            SET status = ?, refunded = ?, finished_at = ?, error_message = ?
            WHERE request_id = ?
            """,
            (next_status, 1 if refund_credit else refunded, now, error_message[:500], request_id),
        )
        conn.execute("COMMIT")

    return get_user_snapshot(user_id)


def create_razorpay_placeholder_order(
    user_id: str,
    email: str,
    display_name: str,
    plan_code: str,
    credits_pack: int,
    amount_paise: int,
) -> dict:
    snapshot = ensure_user_account(user_id, email, display_name)
    initialize_credit_store()
    order_id = f"rzp_placeholder_{uuid.uuid4().hex[:18]}"
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO razorpay_orders (
                order_id, user_id, plan_code, credits_pack, amount_paise, status, created_at, notes
            )
            VALUES (?, ?, ?, ?, ?, 'pending_configuration', ?, ?)
            """,
            (
                order_id,
                user_id,
                plan_code,
                max(0, int(credits_pack or 0)),
                max(0, int(amount_paise or 0)),
                _utc_now(),
                "Razorpay keys not configured yet.",
            ),
        )

    return {
        "order_id": order_id,
        "status": "pending_configuration",
        "plan_code": plan_code,
        "credits_pack": max(0, int(credits_pack or 0)),
        "amount_paise": max(0, int(amount_paise or 0)),
        "message": "Razorpay keys not configured yet. Backend placeholder is ready.",
        "account": snapshot.to_dict(),
    }


def release_stuck_hits(max_age_seconds: int = 1800) -> int:
    initialize_credit_store()
    threshold = time.time() - max(60, max_age_seconds)
    reclaimed = 0

    with _connect() as conn:
        rows = conn.execute(
            "SELECT request_id, user_id, created_at FROM usage_hits WHERE status = 'in_progress'"
        ).fetchall()

        for row in rows:
            try:
                created_at = datetime.fromisoformat(str(row["created_at"])).timestamp()
            except Exception:
                created_at = 0
            if created_at and created_at < threshold:
                try:
                    finish_hit(str(row["user_id"]), str(row["request_id"]), ok=False, error_message="Recovered stale in-progress hit.")
                    reclaimed += 1
                except Exception:
                    continue

    return reclaimed
