import concurrent.futures
import os
import shutil
import subprocess
import tempfile
import time

from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.http import MediaIoBaseDownload

from config.global_config import DEFAULT_BUCKET, creds, drive_service, storage_client
from utils.transcribe import transcribe_segment


def process_drive_file(fileId: str, bucketName: str = None):
    """
    파일 처리 서비스:
        ├── Google Drive 파일 메타데이터 획득
        ├── 파일 다운로드 및 Cloud Storage 업로드
        ├── MP4 → MP3 변환
        ├── MP3 분할 및 FLAC 변환
        ├── FLAC 파일 Cloud Storage 업로드
        ├── 병렬 Speech-to-Text 전사 처리 (transcribe_segment 호출)
        ├── 전사 결과 결합 및 JSON 응답 반환
        └── 자원 정리 (업로드 파일 제거, 임시 파일 삭제)
    """
    start_time = time.time()
    target_bucket = bucketName if bucketName else DEFAULT_BUCKET
    bucket = storage_client.bucket(target_bucket)
    uploaded_files = []

    local_mp4_path = None
    full_mp3_path = None
    split_dir = None

    try:
        # 1. Google Drive 파일 메타데이터 획득
        meta_response = (
            drive_service.files()
            .get(fileId=fileId, fields="id, name, mimeType")
            .execute()
        )
        video_name = meta_response.get("name")
        if not video_name:
            raise Exception("파일 이름을 가져올 수 없습니다.")

        # 2. 파일 다운로드 및 Cloud Storage 업로드
        request_drive = drive_service.files().get_media(fileId=fileId)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_mp4:
            downloader = MediaIoBaseDownload(tmp_mp4, request_drive)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            local_mp4_path = tmp_mp4.name

        mp4_file_name = f"temp/{fileId}_{video_name}"
        blob_mp4_name = mp4_file_name + ".mp4"
        blob_mp4 = bucket.blob(blob_mp4_name)
        blob_mp4.upload_from_filename(local_mp4_path)
        uploaded_files.append(blob_mp4_name)

        # 3. MP4 → MP3 변환
        full_mp3_path = tempfile.mktemp(suffix=".mp3")
        full_mp3_file_name = mp4_file_name.replace(".mp4", ".mp3")
        cmd_full = [
            "ffmpeg",
            "-i",
            local_mp4_path,
            "-vn",
            "-acodec",
            "libmp3lame",
            full_mp3_path,
        ]
        result_full = subprocess.run(cmd_full, capture_output=True, text=True)
        if result_full.returncode != 0:
            raise Exception(f"전체 FFmpeg 변환 오류: {result_full.stderr}")

        # 4. MP3 분할 및 FLAC 변환
        split_dir = tempfile.mkdtemp()
        split_pattern = os.path.join(split_dir, "segment_%03d.mp3")
        split_cmd = [
            "ffmpeg",
            "-i",
            full_mp3_path,
            "-f",
            "segment",
            "-segment_time",
            "300",
            "-c",
            "copy",
            split_pattern,
        ]
        result_split = subprocess.run(split_cmd, capture_output=True, text=True)
        if result_split.returncode != 0:
            raise Exception(f"FFmpeg 분할 오류: {result_split.stderr}")
        segments = sorted(
            [
                os.path.join(split_dir, f)
                for f in os.listdir(split_dir)
                if f.endswith(".mp3")
            ]
        )

        flac_segments = []
        for seg in segments:
            flac_path = seg.rsplit(".", 1)[0] + ".flac"
            cmd_convert = ["ffmpeg", "-i", seg, "-acodec", "flac", flac_path]
            result_convert = subprocess.run(cmd_convert, capture_output=True, text=True)
            if result_convert.returncode != 0:
                raise Exception(f"FLAC 변환 오류: {result_convert.stderr}")
            flac_segments.append(flac_path)

        # 5. FLAC 파일 Cloud Storage 업로드 및 병렬 전사 처리
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
                seg_gs_uri = f"gs://{target_bucket}/{seg_file_name}"
                future = executor.submit(
                    transcribe_segment, seg_file_name, seg_gs_uri, token, i, 10, 1000
                )
                future_to_index[future] = i

            for future in concurrent.futures.as_completed(future_to_index):
                i = future_to_index[future]
                try:
                    seg_index, transcript = future.result()
                    transcriptions.append((seg_index, transcript))
                except Exception as exc:
                    raise Exception(f"세그먼트 {i} 작업 중 오류 발생: {exc}")

        # 6. 전사 결과 결합 및 반환
        combined_transcription = "\n".join(
            [t[1] for t in sorted(transcriptions, key=lambda x: x[0])]
        )
        not_finished_segments = [i for i, _ in transcriptions if i is None]
        taken_time = time.time() - start_time

        result = {
            "takentime": taken_time,
            "mp4FileName": blob_mp4_name,
            "fullMp3GsUri": f"gs://{target_bucket}/{full_mp3_file_name}",
            "transcription": combined_transcription,
            "not-finished-segments": not_finished_segments,
        }
        return result

    finally:
        # 7. 자원 정리 (업로드 파일 제거, 임시 파일 삭제)
        for blob_name in uploaded_files:
            try:
                bucket.blob(blob_name).delete()
            except Exception:
                pass

        if local_mp4_path and os.path.exists(local_mp4_path):
            os.remove(local_mp4_path)
        if full_mp3_path and os.path.exists(full_mp3_path):
            os.remove(full_mp3_path)
        if split_dir and os.path.exists(split_dir):
            shutil.rmtree(split_dir)
