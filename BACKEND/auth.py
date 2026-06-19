from dataclasses import dataclass

import requests
from dotenv import load_dotenv
from firebase_admin import auth as firebase_auth
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from firebase_setup import (
    FIREBASE_APP_ID,
    FIREBASE_PROJECT_ID,
    FIREBASE_WEB_API_KEY,
    FOUNDER_EMAIL,
    FOUNDER_USER_ID,
    initialize_firebase_admin,
)

load_dotenv()

FIREBASE_ISSUER = f"https://securetoken.google.com/{FIREBASE_PROJECT_ID}"


@dataclass
class VerifiedIdentity:
    is_authenticated: bool = False
    user_id: str = ""
    user_name: str = ""
    user_email: str = ""
    session_id: str = ""
    provider: str = "firebase"
    is_founder: bool = False


def _extract_bearer_token(auth_header: str) -> str:
    if not auth_header:
        return ""

    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer":
        return ""
    return token.strip()


def _extract_best_name(claims: dict, claimed_user_name: str = "") -> str:
    if claimed_user_name.strip():
        return claimed_user_name.strip()

    for key in ("name", "display_name", "displayName"):
        value = str(claims.get(key) or "").strip()
        if value:
            return value

    first_name = str(claims.get("first_name") or "").strip()
    last_name = str(claims.get("last_name") or "").strip()
    combined = " ".join(part for part in [first_name, last_name] if part).strip()
    if combined:
        return combined

    email = _extract_best_email(claims)
    return email.split("@", 1)[0] if email and "@" in email else ""


def _extract_best_email(claims: dict) -> str:
    for key in ("email", "email_address", "primary_email_address"):
        value = str(claims.get(key) or "").strip().lower()
        if value:
            return value
    return ""


def _mark_founder(user_id: str, email: str) -> bool:
    return (email or "").strip().lower() == FOUNDER_EMAIL or (user_id or "").strip() == FOUNDER_USER_ID


def _validate_firebase_claims(claims: dict) -> dict:
    issuer = str(claims.get("iss") or "").strip()
    audience = str(claims.get("aud") or "").strip()
    user_id = str(claims.get("uid") or claims.get("sub") or "").strip()

    if issuer != FIREBASE_ISSUER:
        raise ValueError(f"Unexpected Firebase issuer: {issuer}")

    if audience not in {FIREBASE_PROJECT_ID, FIREBASE_APP_ID}:
        raise ValueError(f"Unexpected Firebase audience: {audience}")

    if not user_id:
        raise ValueError("Firebase token did not include a user id")

    claims["uid"] = user_id
    return claims


def _verify_with_admin_sdk(token: str) -> dict:
    app = initialize_firebase_admin()
    if not app:
        raise ValueError("Firebase Admin SDK is not configured")
    claims = firebase_auth.verify_id_token(token, app=app)
    return _validate_firebase_claims(claims)


def _verify_with_google_public_keys(token: str) -> dict:
    request = google_requests.Request()
    errors = []
    for audience in (FIREBASE_PROJECT_ID, FIREBASE_APP_ID, None):
        try:
            claims = google_id_token.verify_firebase_token(token, request, audience=audience)
            return _validate_firebase_claims(claims)
        except Exception as exc:
            errors.append(str(exc))
    raise ValueError("; ".join(errors) if errors else "Firebase public-key verification failed")


def _verify_with_rest_lookup(token: str) -> dict:
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_WEB_API_KEY}"
    response = requests.post(url, json={"idToken": token}, timeout=10)
    response.raise_for_status()
    payload = response.json()
    users = payload.get("users") or []
    if not users:
        raise ValueError("Firebase REST lookup returned no users")
    user = users[0]
    return {
        "uid": str(user.get("localId") or "").strip(),
        "email": str(user.get("email") or "").strip().lower(),
        "name": str(user.get("displayName") or "").strip(),
        "iss": FIREBASE_ISSUER,
        "aud": FIREBASE_PROJECT_ID,
    }


def verify_firebase_session_token(token: str) -> dict:
    verifiers = [
        _verify_with_admin_sdk,
        _verify_with_google_public_keys,
        _verify_with_rest_lookup,
    ]
    last_error = None
    for verifier in verifiers:
        try:
            return verifier(token)
        except Exception as exc:
            last_error = exc
    raise ValueError(f"Firebase token verification failed: {last_error}")


def verify_request_identity(
    auth_header: str,
    claimed_user_id: str = "",
    claimed_user_name: str = "",
) -> VerifiedIdentity:
    token = _extract_bearer_token(auth_header)
    if not token:
        return VerifiedIdentity()

    try:
        claims = verify_firebase_session_token(token)
    except Exception as exc:
        print(f"⚠️ Firebase token verification failed: {exc}")
        return VerifiedIdentity()

    verified_user_id = str(claims.get("uid") or claims.get("sub") or "").strip()
    if not verified_user_id:
        return VerifiedIdentity()

    trusted_name = _extract_best_name(
        claims,
        claimed_user_name if not claimed_user_id or claimed_user_id == verified_user_id else "",
    )
    trusted_email = _extract_best_email(claims)
    is_founder = _mark_founder(verified_user_id, trusted_email)

    return VerifiedIdentity(
        is_authenticated=True,
        user_id=verified_user_id,
        user_name=trusted_name,
        user_email=trusted_email,
        session_id=str(claims.get("session_id") or claims.get("auth_time") or ""),
        provider="firebase",
        is_founder=is_founder,
    )
