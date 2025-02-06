# 베이스 이미지: Python 3.11 slim
FROM python:3.11-slim

# 환경 변수 설정: 바이트코드 생성 방지, stdout/stderr 버퍼링 해제
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 작업 디렉터리 생성 및 설정
WORKDIR /app

# 시스템 의존성 설치 (필요한 경우, 예: ffmpeg 등)
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

# 애플리케이션 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# Cloud Run에서는 PORT 환경 변수가 자동으로 설정됩니다.
# Uvicorn을 사용하여 FastAPI 앱 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]