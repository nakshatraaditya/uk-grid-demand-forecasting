#!/usr/bin/env bash
set -euo pipefail
export AWS_REGION="${AWS_REGION:-eu-west-2}"
ENDPOINT_NAME="griddemand-serverless"
ENDPOINT_CONFIG="griddemand-serverless-config"
MODEL_NAME="griddemand-lgbm"

aws sagemaker delete-endpoint --endpoint-name "$ENDPOINT_NAME" --region "$AWS_REGION" 2>/dev/null || true
aws sagemaker delete-endpoint-config --endpoint-config-name "$ENDPOINT_CONFIG" --region "$AWS_REGION" 2>/dev/null || true
aws sagemaker delete-model --model-name "$MODEL_NAME" --region "$AWS_REGION" 2>/dev/null || true
echo "Torn down."
