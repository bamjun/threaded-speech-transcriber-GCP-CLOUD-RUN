import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from schemas.ai_prompt import PromptRequest
from services.ai_prompt_service import call_ai_prompt
from services.clova_stt_service import process_drive_file_by_ncp_clova

load_dotenv()

app = FastAPI()


google_api_key = os.getenv("google_api_key")


@app.get("/uploadFromDriveToGCS")
async def upload_from_drive_to_gcs(
    fileId: str = Query(..., description="Google Drive 파일 ID"),
    bucketName: str = Query(None, description="Cloud Storage 버킷 이름 (선택)"),
):
    try:
        # result = process_drive_file(fileId, bucketName)
        result = process_drive_file_by_ncp_clova(fileId, bucketName)

        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# @app.get("/transcribe")
# async def upload_from_drive_to_gcs(
#     fileId: str = Query(..., description="Google Drive 파일 ID"),
#     bucketName: str = Query(None, description="Cloud Storage 버킷 이름 (선택)")
#     row: int = Query(None, description="행 번호")
#     sheetId: str = Query(None, description="시트 ID")

# ):
#     try:


@app.get("/test-ncp")
async def test_ncp():
    try:
        result = process_drive_file_by_ncp_clova("1234567890", "test-bucket")
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/transcribe-diarization-by-ncp-clova")
async def transcribe_diarization_by_ncp_clova(
    fileId: str = Query(..., description="Google Drive 파일 ID"),
    bucketName: str = Query(None, description="Cloud Storage 버킷 이름 (선택)"),
):
    try:
        result = process_drive_file_by_ncp_clova(fileId, bucketName)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ai-prompt")
async def ai_prompt(prompt_request: PromptRequest):
    try:
        result = call_ai_prompt(prompt_request.prompt, google_api_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return JSONResponse(content=result)


@app.get("/health")
async def health():
    return JSONResponse(content={"status": "ok"})


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
