import os
import io
import tempfile
import subprocess
import time
import requests
import shutil
import concurrent.futures

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.cloud import storage
from google.auth.transport.requests import Request as GoogleRequest

app = FastAPI()

# OAuth 범위 및 서비스 계정 키 파일
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/devstorage.read_write',
    'https://www.googleapis.com/auth/cloud-platform'
]
SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "./service-account.json")

# Google Drive API 클라이언트 생성
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
drive_service = build('drive', 'v3', credentials=creds)

# Cloud Storage 클라이언트 생성
storage_client = storage.Client(credentials=creds, project="arched-catwalk-449515-e1")

DEFAULT_BUCKET = os.environ.get("BUCKET_NAME", "meet-temp-speech-to-text")

# Speech API URL (beta 버전)
SPEECH_URL = "https://speech.googleapis.com/v1p1beta1/speech:longrunningrecognize"

def transcribe_segment(seg_file_name, seg_gs_uri, token, segment_index, polling_interval=10, max_attempts=1000):
    """
    분할된 오디오 파일에 대해 Speech-to-Text API 요청을 보내고, 폴링하여 전사 결과를 반환하는 함수.
    최대 polling 횟수를 60회로 설정하여, 최대 10분 동안 작업이 완료되길 기다립니다.
    """
    headers = {"Authorization": f"Bearer {token}"}
    seg_speech_request = {
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
            "uri": seg_gs_uri
        }
    }
    print(f"[세그먼트 {segment_index}] Speech 요청 전송: {seg_file_name}")
    response = requests.post(SPEECH_URL, json=seg_speech_request, headers=headers)
    result = response.json()
    if "name" not in result:
        raise Exception(f"[세그먼트 {segment_index}] Speech API 호출 실패: {response.text}")
    operation_name = result["name"]
    operation_url = f"https://speech.googleapis.com/v1/operations/{operation_name}"
    
    attempt = 0
    operation_done = False  # operation_done 변수 초기화
    while attempt < max_attempts and not operation_done:
        time.sleep(polling_interval)
        op_response = requests.get(operation_url, headers=headers)
        op_result = op_response.json()
        print(f"[세그먼트 {segment_index}] 폴링 응답 (시도 {attempt+1}): {op_result}")
        
        if op_result.get("done"):
            operation_done = True
            if "error" in op_result:
                raise Exception(f"[세그먼트 {segment_index}] Speech API 작업 에러: {op_result['error'].get('message', 'Unknown error')}")
            if op_result.get("response") and op_result["response"].get("results"):
                conversation = ""
                SEGMENT_DURATION = 300.0  # 각 세그먼트의 길이 (초 단위)
                for result in op_result["response"]["results"]:
                    alternative = result.get("alternatives", [])[0]
                    transcript = alternative.get("transcript", "").strip()
                    # transcript가 비어 있으면 해당 결과는 건너뛰기
                    if not transcript:
                        continue
                        
                    # "words" 배열이 있다면 첫 단어의 startTime을 사용, 없으면 0으로 설정
                    if "words" in alternative and alternative["words"]:
                        first_word = alternative["words"][0]
                        start_time_str = first_word.get("startTime", "0s")
                        if start_time_str.endswith("s"):
                            start_time = float(start_time_str.rstrip("s"))
                        else:
                            start_time = float(start_time_str)
                    else:
                        start_time = 0.0

                    cumulative_time = segment_index * SEGMENT_DURATION + start_time
                    cumulative_time_formatted = time.strftime("%H:%M:%S", time.gmtime(cumulative_time))
                    conversation += f"[{cumulative_time_formatted}] {transcript}\n"
                transcription = conversation.strip()
                print(f"[세그먼트 {segment_index}] 전사 결과: {transcription}")
                return (segment_index, transcription)
            raise Exception(f"[세그먼트 {segment_index}] 작업 완료되었으나 전사 결과가 비어 있습니다.")
        attempt += 1
    raise Exception(f"[세그먼트 {segment_index}] Speech-to-Text 작업 타임아웃")

@app.get("/uploadFromDriveToGCS")
@app.post("/uploadFromDriveToGCS")
async def upload_from_drive_to_gcs(
    fileId: str = Query(..., description="Google Drive 파일 ID"),
    bucketName: str = Query(None, description="Cloud Storage 버킷 이름 (선택)")
):
    start_time = time.time()
    target_bucket = bucketName if bucketName else DEFAULT_BUCKET
    print(f"사용할 버킷: {target_bucket}")

    # Cloud Storage 버킷 객체와 업로드된 파일명을 저장할 리스트 초기화
    bucket = storage_client.bucket(target_bucket)
    uploaded_files = []

    # 임시 파일 및 디렉터리 경로 변수들 초기화
    local_mp4_path = None
    full_mp3_path = None
    split_dir = None

    try:
        # 1. Google Drive에서 파일 메타데이터 가져오기
        meta_response = drive_service.files().get(
            fileId=fileId, fields="id, name, mimeType"
        ).execute()
        video_name = meta_response.get("name")
        if not video_name:
            raise Exception("파일 이름을 가져올 수 없습니다.")
        print("Drive 파일 이름:", video_name)
        
        # 2. Google Drive에서 MP4 파일 다운로드
        request_drive = drive_service.files().get_media(fileId=fileId)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_mp4:
            downloader = MediaIoBaseDownload(tmp_mp4, request_drive)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            local_mp4_path = tmp_mp4.name
        print("로컬에 MP4 저장 완료:", local_mp4_path)
        
        # 3. Cloud Storage에 MP4 파일 업로드 (원본 보관)
        mp4_file_name = f"temp/{fileId}_{video_name}"
        blob_mp4_name = mp4_file_name + ".mp4"
        blob_mp4 = bucket.blob(blob_mp4_name)
        blob_mp4.upload_from_filename(local_mp4_path)
        uploaded_files.append(blob_mp4_name)
        print("Cloud Storage에 MP4 업로드 완료:", blob_mp4_name)
        
        # 4. MP4 → 전체 MP3 변환
        full_mp3_path = tempfile.mktemp(suffix=".mp3")
        full_mp3_file_name = mp4_file_name.replace(".mp4", ".mp3")
        cmd_full = ["ffmpeg", "-i", local_mp4_path, "-vn", "-acodec", "libmp3lame", full_mp3_path]
        print("실행할 FFmpeg 전체 MP3 변환 명령어:", " ".join(cmd_full))
        result_full = subprocess.run(cmd_full, capture_output=True, text=True)
        if result_full.returncode != 0:
            raise Exception(f"전체 FFmpeg 변환 오류: {result_full.stderr}")
        print("전체 FFmpeg 변환 완료:", result_full.stdout)
        
        # 5. 전체 MP3 파일을 6분(360초) 단위로 분할
        split_dir = tempfile.mkdtemp()
        split_pattern = os.path.join(split_dir, "segment_%03d.mp3")
        split_cmd = ["ffmpeg", "-i", full_mp3_path, "-f", "segment", "-segment_time", "300", "-c", "copy", split_pattern]
        print("실행할 ffmpeg 분할 명령어:", " ".join(split_cmd))
        result_split = subprocess.run(split_cmd, capture_output=True, text=True)
        if result_split.returncode != 0:
            raise Exception(f"FFmpeg 분할 오류: {result_split.stderr}")
        segments = sorted([os.path.join(split_dir, f) for f in os.listdir(split_dir) if f.endswith(".mp3")])
        print("분할된 MP3 파일들:", segments)
        
        # 5-1. 분할된 MP3 파일들을 FLAC으로 변환
        flac_segments = []
        for seg in segments:
            flac_path = seg.rsplit(".", 1)[0] + ".flac"
            cmd_convert = ["ffmpeg", "-i", seg, "-acodec", "flac", flac_path]
            print("실행할 ffmpeg FLAC 변환 명령어:", " ".join(cmd_convert))
            result_convert = subprocess.run(cmd_convert, capture_output=True, text=True)
            if result_convert.returncode != 0:
                raise Exception(f"FLAC 변환 오류: {result_convert.stderr}")
            flac_segments.append(flac_path)
        print("변환된 FLAC 파일들:", flac_segments)
        
        # 6. Speech-to-Text 작업 병렬 처리 (각 세그먼트 10초 간격, 최대 10분 대기 per segment)
        creds.refresh(GoogleRequest())
        token = creds.token
        transcriptions = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_index = {}
            for i, seg_path in enumerate(flac_segments):
                seg_file_name = f"{mp4_file_name}_seg_{i:03d}.flac"
                blob_seg = bucket.blob(seg_file_name)
                blob_seg.upload_from_filename(seg_path)
                uploaded_files.append(seg_file_name)
                print(f"Cloud Storage에 분할 파일 업로드 완료: {seg_file_name}")
                seg_gs_uri = f"gs://{target_bucket}/{seg_file_name}"
                future = executor.submit(transcribe_segment, seg_file_name, seg_gs_uri, token, i, 10, 1000)
                future_to_index[future] = i
            
            for future in concurrent.futures.as_completed(future_to_index):
                i = future_to_index[future]
                try:
                    seg_index, transcript = future.result()
                    transcriptions.append((seg_index, transcript))
                except Exception as exc:
                    raise Exception(f"세그먼트 {i} 작업 중 오류 발생: {exc}")
        
        combined_transcription = "\n".join([t[1] for t in sorted(transcriptions, key=lambda x: x[0])])
        print("전체 전사 결과:", combined_transcription)
        
        not_finished_segments = [i for i, _ in transcriptions if i is None]
        print("미완료 세그먼트:", not_finished_segments)
        
        taken_time = time.time() - start_time
        return JSONResponse(content={
            "takentime": taken_time,
            "mp4FileName": blob_mp4_name,
            "fullMp3GsUri": f"gs://{target_bucket}/{full_mp3_file_name}",
            "transcription": combined_transcription,
            "not-finished-segments": not_finished_segments
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cloud Storage에 업로드된 파일 삭제
        for blob_name in uploaded_files:
            try:
                bucket.blob(blob_name).delete()
                print(f"Cloud Storage에서 파일 삭제 완료: {blob_name}")
            except Exception as ex:
                print(f"Cloud Storage에서 파일 삭제 실패: {blob_name}, 에러: {ex}")

        # 로컬 임시 파일 및 디렉터리 삭제
        if local_mp4_path and os.path.exists(local_mp4_path):
            os.remove(local_mp4_path)
            print(f"로컬 MP4 파일 삭제 완료: {local_mp4_path}")
        if full_mp3_path and os.path.exists(full_mp3_path):
            os.remove(full_mp3_path)
            print(f"로컬 MP3 파일 삭제 완료: {full_mp3_path}")
        if split_dir and os.path.exists(split_dir):
            shutil.rmtree(split_dir)
            print(f"임시 디렉터리 삭제 완료: {split_dir}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
