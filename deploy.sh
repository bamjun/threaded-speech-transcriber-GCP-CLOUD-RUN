gcloud builds submit --tag gcr.io/arched-catwalk-449515-e1/fastapi-upload-from-drive-to-gcs
gcloud run deploy fastapi-upload-from-drive-to-gcs \
  --image gcr.io/arched-catwalk-449515-e1/fastapi-upload-from-drive-to-gcs \
  --platform managed \
  --region asia-northeast3 \
  --allow-unauthenticated