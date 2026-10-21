import os

import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# 프로젝트 폴더의 .env 설정 읽기
load_dotenv()

PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")


def get_firestore_client():
	"""Firebase Admin SDK를 초기화하고 Firestore 클라이언트를 반환합니다."""
	if not firebase_admin._apps:
		options = {"projectId": PROJECT_ID} if PROJECT_ID else None
		firebase_admin.initialize_app(
			credentials.ApplicationDefault(),
			options=options,
		)

	return firestore.client()
