import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")

# 프로젝트 루트에 있는 서비스 계정 JSON 파일
BASE_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = BASE_DIR / (
    "ai-stock-helper-27fb1-firebase-adminsdk-fbsvc-25cfe6392c.json"
)


def get_firestore_client():
    if not firebase_admin._apps:
        if not CREDENTIALS_PATH.exists():
            raise FileNotFoundError(
                f"Firebase 인증 파일을 찾을 수 없습니다: {CREDENTIALS_PATH.name}"
            )

        credential = credentials.Certificate(str(CREDENTIALS_PATH))
        options = {"projectId": PROJECT_ID} if PROJECT_ID else None

        firebase_admin.initialize_app(
            credential,
            options=options,
        )

    return firestore.client()