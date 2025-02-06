import os
import io
import tempfile
import subprocess
import time
import requests

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.cloud import storage
from google.auth.transport.requests import Request as GoogleRequest

app = FastAPI()

# OAuth 범위 및 서비스 계정 키 파일 (환경 변수 또는 직접 지정)
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/devstorage.read_write',  # Cloud Storage 권한 추가
    'https://www.googleapis.com/auth/cloud-platform'          # Speech API 인증 범위 추가
]
SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "./service-account.json")

# Google Drive API 클라이언트 생성 (서비스 계정 자격 증명을 사용)
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
drive_service = build('drive', 'v3', credentials=creds)

# Cloud Storage 클라이언트 생성 (기본 ADC 사용)
storage_client = storage.Client(credentials=creds, project="arched-catwalk-449515-e1")

# 기본 버킷 이름 (환경 변수 BUCKET_NAME이 설정되어 있지 않으면 기본값 사용)
DEFAULT_BUCKET = os.environ.get("BUCKET_NAME", "meet-temp-speech-to-text")


@app.get("/uploadFromDriveToGCS")
@app.post("/uploadFromDriveToGCS")
async def upload_from_drive_to_gcs(
    fileId: str = Query(..., description="Google Drive 파일 ID"),
    bucketName: str = Query(None, description="Cloud Storage 버킷 이름 (선택)")
):
    start_time = time.time()
    # bucketName이 전달되지 않으면 기본값 사용
    target_bucket = bucketName if bucketName else DEFAULT_BUCKET
    print(f"{target_bucket=}")
    try:
        # 1. Google Drive에서 파일 메타데이터 가져오기
        meta_response = drive_service.files().get(
            fileId=fileId, fields="id, name, mimeType"
        ).execute()
        video_name = meta_response.get("name")
        if not video_name:
            raise Exception("파일 이름을 가져올 수 없습니다.")
        print("Drive 파일 이름:", video_name)
        
        # 2. Google Drive에서 파일 콘텐츠 다운로드
        request = drive_service.files().get_media(fileId=fileId)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_mp4:
            downloader = MediaIoBaseDownload(tmp_mp4, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            local_mp4_path = tmp_mp4.name
        print("로컬에 MP4 저장 완료:", local_mp4_path)
        
        # 3. Cloud Storage에 MP4 파일 업로드
        mp4_file_name = f"temp/{fileId}_{video_name}"
        print("mp4_file_name:", mp4_file_name)
        bucket = storage_client.bucket(target_bucket)
        print("bucket:", bucket)
        blob_mp4 = bucket.blob(mp4_file_name)
        print("blob_mp4:", blob_mp4)
        try:
            blob_mp4.upload_from_filename(local_mp4_path)
            print("Cloud Storage에 MP4 업로드 완료:", mp4_file_name)
        except Exception as upload_err:
            print("MP4 업로드 중 오류 발생:", upload_err)
            raise
        
        # 4. MP4 → FLAC 변환 (FFmpeg 사용)
        flac_file_name = mp4_file_name.replace(".mp4", ".flac")
        local_flac_path = tempfile.mktemp(suffix=".flac")
        cmd = ["ffmpeg", "-i", local_mp4_path, "-vn", "-acodec", "flac", local_flac_path]
        print("실행할 FFmpeg 명령어:", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"FFmpeg 변환 오류: {result.stderr}")
        print("FFmpeg 변환 완료:", result.stdout)
        
        # 5. Cloud Storage에 FLAC 파일 업로드
        blob_flac = bucket.blob(flac_file_name)
        blob_flac.upload_from_filename(local_flac_path)
        print("Cloud Storage에 FLAC 업로드 완료:", flac_file_name)
        flac_gs_uri = f"gs://{target_bucket}/{flac_file_name}"
        print("FLAC 파일 gsUri:", flac_gs_uri)
        
        # 6. Speech-to-Text API 호출 (FLAC 파일 사용)
        # 자격증명을 갱신하여 액세스 토큰 획득
        creds.refresh(GoogleRequest())
        token = creds.token

        speech_url = "https://speech.googleapis.com/v1p1beta1/speech:longrunningrecognize"
        speech_request = {
            "config": {
                "encoding": "FLAC",
                "languageCode": "ko-KR",
                "useEnhanced": True,
                "audioChannelCount": 2,
                "enableSpeakerDiarization": True,
                "diarizationSpeakerCount": 2,
                "enableWordTimeOffsets": True
            },
            "audio": {
                "uri": flac_gs_uri
            }
        }
        headers = {"Authorization": f"Bearer {token}"}
        speech_response = requests.post(speech_url, json=speech_request, headers=headers)
        speech_result = speech_response.json()
        print("Speech API 응답:", speech_result)
        
        if "name" not in speech_result:
            raise Exception("Speech-to-Text API 호출 실패: " + speech_response.text)
        operation_name = speech_result["name"]
        
        # 7. 롱러닝 작업 결과 폴링
        operation_url = f"https://speech.googleapis.com/v1/operations/{operation_name}"
        polling_interval = 10  # 초 단위
        max_attempts = 60 * 18  # 최대 180분 대기
        attempt = 0
        operation_done = False
        transcription = ""
        
        while attempt < max_attempts and not operation_done:
            time.sleep(polling_interval)
            op_response = requests.get(operation_url, headers=headers)
            op_result = op_response.json()
            print("폴링 응답:", op_result)
            
            if op_result.get("done"):
                operation_done = True
                if "error" in op_result:
                    raise Exception("Speech API 작업 에러: " + op_result["error"].get("message", "Unknown error"))
                if op_result.get("response") and op_result["response"].get("results"):
                    last_result = op_result["response"]["results"][-1]
                    alternatives = last_result.get("alternatives", [])
                    if alternatives:
                        first_alternative = alternatives[0]
                        if "words" in first_alternative:
                            words = first_alternative["words"]
                            conversation = ""
                            current_speaker = None
                            speaker_mapping = {}
                            next_label_code = ord('a')
                            for word_obj in words:
                                speaker = word_obj.get("speakerTag")
                                if speaker not in speaker_mapping:
                                    speaker_mapping[speaker] = chr(next_label_code)
                                    next_label_code += 1
                                if speaker != current_speaker:
                                    current_speaker = speaker
                                    conversation += "\n" + speaker_mapping[speaker] + ": "
                                conversation += word_obj.get("word", "") + " "
                            transcription = conversation.strip()
                        else:
                            transcription = first_alternative.get("transcript", "")
            attempt += 1
        
        if not operation_done:
            raise Exception("Speech-to-Text 작업이 타임아웃되었습니다.")
        
        # 8. 임시 파일 삭제 (선택)
        os.remove(local_mp4_path)
        os.remove(local_flac_path)
        
        return JSONResponse(content={
            "takentime": time.time() - start_time,
            "mp4FileName": mp4_file_name,
            "flacGsUri": flac_gs_uri,
            "transcription": transcription
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    # 로컬 실행 시 uvicorn을 사용
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
