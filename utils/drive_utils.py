import io
import os
import tempfile
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


def get_google_drive_service() -> Any:
    """Google Drive API 서비스 객체를 생성합니다."""
    try:
        # 서비스 계정 키 파일 경로
        credentials = service_account.Credentials.from_service_account_file(
            "service-account.json",  # 서비스 계정 키 파일 경로
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )

        return build("drive", "v3", credentials=credentials)
    except Exception as e:
        raise Exception(f"Drive 서비스 생성 실패: {str(e)}")


def download_file_from_drive(file_id: str) -> str:
    """
    Google Drive에서 파일을 다운로드하고 임시 파일 경로를 반환합니다.

    Args:
        file_id (str): Google Drive 파일 ID

    Returns:
        str: 다운로드된 임시 파일의 경로

    Raises:
        Exception: 파일 다운로드 실패 시 발생
    """
    try:
        # Drive API 서비스 생성
        service = get_google_drive_service()

        # 파일 메타데이터 가져오기
        file_metadata = service.files().get(fileId=file_id).execute()
        file_name = file_metadata.get("name", "downloaded_file")

        # 파일 확장자 확인 및 임시 파일 생성
        file_ext = os.path.splitext(file_name)[1]
        if not file_ext:
            file_ext = ".wav"  # 기본 확장자

        # 임시 파일 생성
        temp_file = tempfile.NamedTemporaryFile(suffix=file_ext, delete=False)
        temp_file_path = temp_file.name

        # 파일 다운로드
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)

        done = False
        while done is False:
            status, done = downloader.next_chunk()
            if status:
                print(f"다운로드 진행률: {int(status.progress() * 100)}%")

        # 파일 저장
        fh.seek(0)
        with open(temp_file_path, "wb") as f:
            f.write(fh.read())

        print(f"파일 다운로드 완료: {temp_file_path}")
        return temp_file_path

    except Exception as e:
        raise Exception(f"Google Drive 파일 다운로드 실패: {str(e)}")
