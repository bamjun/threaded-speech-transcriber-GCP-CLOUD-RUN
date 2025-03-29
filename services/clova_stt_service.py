import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

import requests
from google.cloud import storage

from utils.drive_utils import download_file_from_drive


class ClovaSpeechClient:
    def __init__(self):
        self.invoke_url = os.getenv(
            "CLOVA_INVOKE_URL", "https://clovaspeech-gw.ncloud.com"
        )
        self.secret = os.getenv("CLOVA_SECRET_KEY")
        if not self.secret:
            raise Exception("CLOVA_SECRET_KEY가 설정되지 않았습니다.")

    def req_upload(
        self, file: str, completion: str = "sync", diarization: Dict = None
    ) -> requests.Response:
        """
        파일 업로드 방식으로 음성 인식을 요청합니다.
        """
        request_body = {
            "language": "ko-KR",
            "completion": completion,
            "wordAlignment": True,
            "fullText": True,
            "diarization": diarization
            or {"enable": True, "speakerCountMin": 2, "speakerCountMax": 2},
        }

        headers = {
            "Accept": "application/json;UTF-8",
            "X-CLOVASPEECH-API-KEY": self.secret,
        }

        print("요청 본문:", json.dumps(request_body, ensure_ascii=False))

        files = {
            "media": open(file, "rb"),
            "params": (
                None,
                json.dumps(request_body, ensure_ascii=False).encode("UTF-8"),
                "application/json",
            ),
        }

        response = requests.post(
            headers=headers, url=f"{self.invoke_url}/recognizer/upload", files=files
        )
        return response


def format_time(ms: int) -> str:
    """
    밀리초를 [HH:MM:SS] 형식으로 변환합니다.
    """
    total_seconds = ms // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"[{hours:02d}:{minutes:02d}:{seconds:02d}]"


def process_drive_file_by_ncp_clova(
    file_id: str, bucket_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Google Drive에서 파일을 다운로드하고 Clova Speech API를 사용하여 화자 분리 음성 인식을 수행합니다.

    Args:
        file_id (str): Google Drive 파일 ID
        bucket_name (Optional[str]): GCS 버킷 이름 (선택사항)

    Returns:
        Dict[str, Any]: 음성 인식 결과를 포함하는 딕셔너리
    """
    local_file_path = None
    try:
        # 1. Google Drive에서 파일 다운로드
        local_file_path = download_file_from_drive(file_id)
        print(f"다운로드된 파일: {local_file_path}")

        # 2. Clova Speech API 클라이언트 생성 및 요청
        client = ClovaSpeechClient()
        response = client.req_upload(
            file=local_file_path, completion="sync", diarization={"enable": True}
        )

        print(f"API 응답 상태 코드: {response.status_code}")
        print(f"API 응답 내용: {response.text}")

        # 3. 응답 처리
        if response.status_code == 200:
            result = response.json()

            # 음성 인식 결과를 시간순으로 포맷팅
            transcription = ""
            if "segments" in result:
                for segment in result["segments"]:
                    start_time = format_time(segment["start"])
                    speaker_name = segment["speaker"]["name"]
                    text = segment["text"]
                    transcription += f"{start_time} speaker {speaker_name} - {text}\n"

            # 4. GCS에 결과 저장 (선택사항)
            if bucket_name:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                result_blob_name = f"clova_results/{file_id}_{timestamp}.json"

                storage_client = storage.Client()
                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob(result_blob_name)

                # 원본 결과와 포맷팅된 텍스트를 모두 저장
                save_result = {
                    "original_result": result,
                    "formatted_transcription": transcription,
                }

                blob.upload_from_string(
                    json.dumps(save_result, ensure_ascii=False),
                    content_type="application/json",
                )

                result["gcs_result_path"] = f"gs://{bucket_name}/{result_blob_name}"

            return {
                "status": "success",
                "message": "음성 인식이 완료되었습니다.",
                "result": result,
                "transcription": transcription,
            }

        else:
            error_msg = f"Clova API 요청 실패: {response.status_code} - {response.text}"
            print(error_msg)
            raise Exception(error_msg)

    except Exception as e:
        error_msg = f"음성 인식 처리 중 오류 발생: {str(e)}"
        print(error_msg)
        raise Exception(error_msg)

    finally:
        # 5. 임시 파일 정리
        if local_file_path and os.path.exists(local_file_path):
            try:
                os.remove(local_file_path)
            except Exception as e:
                print(f"임시 파일 삭제 실패: {e}")
