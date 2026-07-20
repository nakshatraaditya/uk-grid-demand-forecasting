FROM python:3.12-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Layer 1 (slow, cached): dependencies only.
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

# Layer 2 (fast): the exported model. Rebuilding with a new model reuses
COPY model_export /app/model
ENV GRIDDEMAND_MODEL_PATH=/app/model

# Never run as root inside containers(remember that)
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD curl -sf http://localhost:8000/health || exit 1

CMD ["uvicorn", "griddemand.serving.app:app", "--host", "0.0.0.0", "--port", "8000"]