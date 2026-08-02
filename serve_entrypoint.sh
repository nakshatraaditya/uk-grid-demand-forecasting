#!/usr/bin/env bash
# SageMaker calls the image as `docker run <image> serve`. We ignore any
# passed args and always start the API on $PORT (SageMaker expects 8080).
set -e
exec uvicorn griddemand.serving.app:app --host 0.0.0.0 --port "${PORT:-8080}"
