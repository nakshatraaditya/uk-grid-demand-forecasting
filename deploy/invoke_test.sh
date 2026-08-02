#!/usr/bin/env bash
set -euo pipefail
export AWS_REGION="${AWS_REGION:-eu-west-2}"
ENDPOINT_NAME="griddemand-serverless"

cat > /tmp/griddemand_payload.json <<'JSON'
{
  "rows": [
    {
      "lag_48": 28000, "lag_96": 27500, "lag_336": 29000,
      "roll_mean_48": 28200, "roll_max_48": 34000, "roll_min_48": 21000,
      "hour": 18.0, "day_of_week": 2, "is_weekend": 0, "month": 1,
      "hour_sin": -0.7071, "hour_cos": -0.7071,
      "temperature_2m": 6.5, "wind_speed_10m": 18.0, "cloud_cover": 80
    }
  ]
}
JSON

aws sagemaker-runtime invoke-endpoint \
  --endpoint-name "$ENDPOINT_NAME" \
  --region "$AWS_REGION" \
  --content-type application/json \
  --body fileb:///tmp/griddemand_payload.json \
  /tmp/griddemand_response.json >/dev/null

echo "Response:"; cat /tmp/griddemand_response.json; echo
