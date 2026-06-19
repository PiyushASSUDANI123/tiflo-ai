import json
import os
from functools import lru_cache

import firebase_admin
from dotenv import load_dotenv
from firebase_admin import credentials, firestore

load_dotenv()

FIREBASE_WEB_API_KEY = os.getenv("FIREBASE_WEB_API_KEY")
FIREBASE_AUTH_DOMAIN = os.getenv("FIREBASE_AUTH_DOMAIN")
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")
FIREBASE_STORAGE_BUCKET = os.getenv("FIREBASE_STORAGE_BUCKET")
FIREBASE_MESSAGING_SENDER_ID = os.getenv("FIREBASE_MESSAGING_SENDER_ID")
FIREBASE_APP_ID = os.getenv("FIREBASE_APP_ID")
FIREBASE_MEASUREMENT_ID = os.getenv("FIREBASE_MEASUREMENT_ID")

FOUNDER_EMAIL = os.getenv("FOUNDER_EMAIL", "piyushassudani96@gmail.com").strip().lower()
FOUNDER_USER_ID = os.getenv("FOUNDER_USER_ID", "piyush_ceo").strip()
DEFAULT_LOGIN_CREDITS = int(os.getenv("DEFAULT_LOGIN_CREDITS", "25"))


def get_firebase_public_config() -> dict:
    return {
        "apiKey": FIREBASE_WEB_API_KEY,
        "authDomain": FIREBASE_AUTH_DOMAIN,
        "projectId": FIREBASE_PROJECT_ID,
        "storageBucket": FIREBASE_STORAGE_BUCKET,
        "messagingSenderId": FIREBASE_MESSAGING_SENDER_ID,
        "appId": FIREBASE_APP_ID,
        "measurementId": FIREBASE_MEASUREMENT_ID,
    }


@lru_cache(maxsize=1)
def initialize_firebase_admin():
    if firebase_admin._apps:
        return firebase_admin.get_app()

    firebase_raw_data = os.getenv("FIREBASE_JSON", "").strip()
    if firebase_raw_data:
        try:
            cred_dict = json.loads(firebase_raw_data)
            cred = credentials.Certificate(cred_dict)
            app = firebase_admin.initialize_app(cred)
            print("✅ Firebase Admin loaded from FIREBASE_JSON.")
            return app
        except Exception as e:
            print(f"❌ Failed to initialize Firebase Admin from FIREBASE_JSON: {e}")

    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if creds_path and os.path.exists(creds_path):
        try:
            cred = credentials.Certificate(creds_path)
            app = firebase_admin.initialize_app(cred)
            print(f"✅ Firebase Admin loaded from GOOGLE_APPLICATION_CREDENTIALS: {creds_path}")
            return app
        except Exception as e:
            print(f"❌ Failed to initialize Firebase Admin from GOOGLE_APPLICATION_CREDENTIALS: {e}")

    print("⚠️ Firebase Admin credentials not configured. Firestore admin features will stay disabled.")
    return None


@lru_cache(maxsize=1)
def get_firestore_client():
    app = initialize_firebase_admin()
    if not app:
        return None

    try:
        return firestore.client(app=app)
    except Exception as e:
        print(f"⚠️ Failed to create Firestore client: {e}")
        return None
