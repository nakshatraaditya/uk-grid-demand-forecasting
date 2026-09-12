#!/usr/bin/env bash
# Deploy the containerized champion to Google Cloud Run.
# Mirrors deploy_sagemaker.sh: build → push → (re)deploy → smoke-test.
#
# Prereqs: gcloud CLI authenticated, Docker daemon running, project billing enabled.
# Override any variable with an env var of the same name.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?set PROJECT_ID to your GCP project}"
REGION="${REGION:-europe-west2}"
SERVICE_NAME="${SERVICE_NAME:-grid-demand-api}"
AR_REPO="${AR_REPO:-griddemand}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo latest)}"
MEMORY="${MEMORY:-2Gi}"
CPU="${CPU:-1}"
MAX_INSTANCES="${MAX_INSTANCES:-3}"
MIN_INSTANCES="${MIN_INSTANCES:-0}"
CONCURRENCY="${CONCURRENCY:-40}"

IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${SERVICE_NAME}:${IMAGE_TAG}"

echo "==> 1/5  Ensure Artifact Registry repo exists"
gcloud artifacts repositories describe "$AR_REPO" \
  --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1 \
  || gcloud artifacts repositories create "$AR_REPO" \
       --repository-format=docker --location "$REGION" --project "$PROJECT_ID" >/dev/null

echo "==> 2/5  Build linux/amd64 image and push to ${IMAGE_URI}"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet >/dev/null
docker build --platform linux/amd64 -t "$IMAGE_URI" .
docker push "$IMAGE_URI"

echo "==> 3/5  Deploy to Cloud Run"
gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE_URI" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --platform managed \
  --allow-unauthenticated \
  --memory "$MEMORY" \
  --cpu "$CPU" \
  --min-instances "$MIN_INSTANCES" \
  --max-instances "$MAX_INSTANCES" \
  --concurrency "$CONCURRENCY" \
  --port 8000 \
  --quiet >/dev/null

echo "==> 4/5  Resolve service URL"
SERVICE_URL="$(gcloud run services describe "$SERVICE_NAME" \
  --region "$REGION" --project "$PROJECT_ID" --format='value(status.url)')"
echo "    URL: ${SERVICE_URL}"

echo "==> 5/5  Smoke-test /health (allow cold-start ~15s)"
for i in 1 2 3 4 5; do
  if curl -fsS --max-time 20 "${SERVICE_URL}/health" >/dev/null; then
    echo "    /health OK"
    break
  fi
  echo "    attempt $i failed, retrying..."
  sleep 5
done

echo
echo "Deployed. Interactive docs: ${SERVICE_URL}/docs"
