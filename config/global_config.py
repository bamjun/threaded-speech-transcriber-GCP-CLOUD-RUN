import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.cloud import storage

# OAuth 범위 정의
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/devstorage.read_write',
    'https://www.googleapis.com/auth/cloud-platform'
]

# 서비스 계정 파일 경로 (환경 변수 또는 기본값 사용)
SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "./service-account.json")

# 기본 Cloud Storage 버킷 이름
DEFAULT_BUCKET = os.environ.get("BUCKET_NAME", "meet-temp-speech-to-text")

# Speech API URL (베타 버전)
SPEECH_URL = "https://speech.googleapis.com/v1p1beta1/speech:longrunningrecognize"

# 서비스 계정 인증 및 API 클라이언트 생성
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=SCOPES
)

# Google Drive API 클라이언트 생성
drive_service = build('drive', 'v3', credentials=creds)

# Google Cloud Storage 클라이언트 생성
storage_client = storage.Client(credentials=creds, project="arched-catwalk-449515-e1") 