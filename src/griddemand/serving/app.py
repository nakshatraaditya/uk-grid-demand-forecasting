from __future__ import annotations
import logging
from contextlib import asynccontextmanager
import pandas as pd
from fastapi import FastAPI, HTTPException
from griddemand import config
from griddemand.features.build import FEATURE_COLS
from griddemand.models.registry import champion_version, load_champion
from griddemand.serving.schemas import (
    HealthResponse,
    PredictRequest,
    PredictResponse,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        app.state.model = load_champion()
        app.state.model_version = champion_version()
        logger.info("Loaded champion model version %s", app.state.model_version)
    except Exception:
        logger.exception("Failed to load champion model")
        app.state.model = None
        app.state.model_version = None
    yield


app = FastAPI(
    title="Grid Demand Forecast API",
    description="Day-ahead UK national demand forecasts from the registered champion model",
    version="0.1.0",
    lifespan=lifespan,
)
@app.get("/", include_in_schema=False)
def root():
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/docs")

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok" if app.state.model is not None else "degraded",
        model_loaded=app.state.model is not None,
    )


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest) -> PredictResponse:
    if app.state.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    features = pd.DataFrame([r.model_dump() for r in request.rows])[FEATURE_COLS]
    preds = app.state.model.predict(features)

    return PredictResponse(
        predictions_mw=[round(float(p), 1) for p in preds],
        n=len(preds),
        model_name=config.MODEL_NAME,
        model_version=str(app.state.model_version),
    )