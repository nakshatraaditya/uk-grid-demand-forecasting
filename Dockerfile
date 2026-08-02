FROM python:3.12-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY model_export /app/model
ENV GRIDDEMAND_MODEL_PATH=/app/model

COPY serve_entrypoint.sh /app/serve_entrypoint.sh
RUN chmod +x /app/serve_entrypoint.sh

RUN useradd --create-home appuser
USER appuser

ENV PORT=8080
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD curl -sf http://localhost:${PORT}/ping || exit 1

# ENTRYPOINT ignores the `serve` arg SageMaker appends and always runs uvicorn.
ENTRYPOINT ["/app/serve_entrypoint.sh"]
