### toml 에서 requirements.txt 추출할때
uv export -o requirements.txt --no-hashes --no-dev

### 로컬에서 테스트
uv run uvicorn main:app --host 0.0.0.0 --port 8080

### 배포시
gcloud run deploy --source .




# 독커배포
gcloud builds submit --tag gcr.io/PROJECT_ID/IMAGE_NAME
gcloud builds submit --tag gcr.io/arched-catwalk-449515-e1/fastapi-upload-from-drive-to-gcs

# SERVICE_NAME, PROJECT_ID, IMAGE_NAME, 그리고 REGION 값을 본인의 환경에 맞게 변경하세요.
gcloud run deploy SERVICE_NAME \
  --image gcr.io/PROJECT_ID/IMAGE_NAME \
  --platform managed \
  --region REGION \
  --allow-unauthenticated

gcloud run deploy fastapi-upload-from-drive-to-gcs \
  --image gcr.io/arched-catwalk-449515-e1/fastapi-upload-from-drive-to-gcs \
  --platform managed \
  --region asia-northeast3 \
  --allow-unauthenticated

### gcloud 명령어로 인증 전환하기
gsutil은 gcloud로 로그인된 자격 증명을 사용할 수도 있습니다. 예를 들어, 사용자 계정으로 로그인하고 싶다면:
bash
gcloud auth login


또는 서비스 계정으로 전환하려면:
bash
gcloud auth activate-service-account --key-file="/path/to/your/service-account.json"



### 매모리 증가하기
gcloud run services update fastapi-upload-from-drive-to-gcs \
  --memory=1Gi
