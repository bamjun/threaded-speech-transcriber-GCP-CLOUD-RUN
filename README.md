# VIDEO to TRANCRIPT
- google cloud
  - cloud run
  - cloud storage
  - Speech-to-Text API
  - google drive

- python
  - fast api

- ffmpeg

- docker

---

> google drive의 파일ID와 같이 요청이들어오면,
> google drive의 파일ID의 해당 파일을 다운로드 한다.  
> ffmpeg로 동영상을 음성파일 (flac)로 변환하고, 총길이 / 5분 으로 분할 한다.  
> 나눠진 파일을 cloud storage에 올린다.  
> 각 나눠진 파일을 쓰래딩하고, Speech-to-Text API를 통해서, 문자로 변환한다.  
> 작업이 완료돼면 나눠진 텍스트를 합치고 응답을 준다.  




---


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
