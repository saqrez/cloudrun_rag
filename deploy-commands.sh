gcloud run deploy info-chatbot \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --max-instances 1 \
  --min-instances 0