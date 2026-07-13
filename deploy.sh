#!/usr/bin/env bash
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT first}"

REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-rcm-adk-service}"
SERVICE_ACCOUNT_NAME="${SERVICE_ACCOUNT_NAME:-rcm-adk-runner}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT_NAME}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"
COMMON_ENV="GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT},GOOGLE_CLOUD_LOCATION=${REGION},GOOGLE_GENAI_USE_VERTEXAI=True"

gcloud config set project "$GOOGLE_CLOUD_PROJECT"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com

if ! gcloud iam service-accounts describe "$SERVICE_ACCOUNT" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
    --display-name="RCM ADK Cloud Run"
fi

gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/aiplatform.user" \
  --quiet

gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region "$REGION" \
  --service-account "$SERVICE_ACCOUNT" \
  --no-allow-unauthenticated \
  --set-env-vars "${COMMON_ENV},SERVE_WEB_INTERFACE=true"

gcloud run deploy "${SERVICE_NAME}-a2a" \
  --source . \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region "$REGION" \
  --service-account "$SERVICE_ACCOUNT" \
  --command uv \
  --args run,--no-sync,uvicorn,a2a_server:app,--host,0.0.0.0,--port,8080 \
  --no-allow-unauthenticated \
  --set-env-vars "$COMMON_ENV"

gcloud run deploy "${SERVICE_NAME}-mcp" \
  --source . \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region "$REGION" \
  --service-account "$SERVICE_ACCOUNT" \
  --command uv \
  --args run,--no-sync,uvicorn,mcp_server:app,--host,0.0.0.0,--port,8080 \
  --no-allow-unauthenticated \
  --set-env-vars "$COMMON_ENV"
