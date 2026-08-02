#!/usr/bin/env bash
set -euo pipefail

export AWS_REGION="eu-west-2"
export SAGEMAKER_ROLE_ARN="arn:aws:iam::332380490782:role/griddemand-sagemaker-role"

ECR_REPO="griddemand"
IMAGE_TAG="latest"
MODEL_NAME="griddemand-lgbm"
ENDPOINT_CONFIG="griddemand-serverless-config"
ENDPOINT_NAME="griddemand-serverless"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"

echo "==> 1/5  Ensure ECR repo exists"
aws ecr describe-repositories --repository-names "$ECR_REPO" --region "$AWS_REGION" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "$ECR_REPO" --region "$AWS_REGION" >/dev/null

echo "==> 2/5  Build + push image to ECR"
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
docker build --platform linux/amd64 -t "${ECR_REPO}:${IMAGE_TAG}" .
docker tag "${ECR_REPO}:${IMAGE_TAG}" "${ECR_URI}:${IMAGE_TAG}"
docker push "${ECR_URI}:${IMAGE_TAG}"

echo "==> 3/5  (Re)create SageMaker model"
aws sagemaker delete-model --model-name "$MODEL_NAME" --region "$AWS_REGION" 2>/dev/null || true
aws sagemaker create-model \
  --model-name "$MODEL_NAME" \
  --execution-role-arn "$SAGEMAKER_ROLE_ARN" \
  --primary-container "Image=${ECR_URI}:${IMAGE_TAG}" \
  --region "$AWS_REGION" >/dev/null

echo "==> 4/5  (Re)create serverless endpoint config (2GB, max 1 concurrency)"
aws sagemaker delete-endpoint-config --endpoint-config-name "$ENDPOINT_CONFIG" --region "$AWS_REGION" 2>/dev/null || true
aws sagemaker create-endpoint-config \
  --endpoint-config-name "$ENDPOINT_CONFIG" \
  --production-variants "VariantName=AllTraffic,ModelName=${MODEL_NAME},ServerlessConfig={MemorySizeInMB=3072,MaxConcurrency=1}" \
  --region "$AWS_REGION" >/dev/null

echo "==> 5/5  Create or update endpoint"
if aws sagemaker describe-endpoint --endpoint-name "$ENDPOINT_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
  aws sagemaker update-endpoint --endpoint-name "$ENDPOINT_NAME" --endpoint-config-name "$ENDPOINT_CONFIG" --region "$AWS_REGION" >/dev/null
else
  aws sagemaker create-endpoint --endpoint-name "$ENDPOINT_NAME" --endpoint-config-name "$ENDPOINT_CONFIG" --region "$AWS_REGION" >/dev/null
fi

echo "==> Waiting for endpoint to be InService (a few minutes)..."
aws sagemaker wait endpoint-in-service --endpoint-name "$ENDPOINT_NAME" --region "$AWS_REGION"
echo "InService: $ENDPOINT_NAME  (region $AWS_REGION)"
