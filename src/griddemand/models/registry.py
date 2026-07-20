from __future__ import annotations
import os
from pathlib import Path
import lightgbm as lgb
import mlflow
from griddemand import config

MODEL_PATH_ENV = "GRIDDEMAND_MODEL_PATH"


def load_champion() -> lgb.Booster:
    model_path = os.getenv(MODEL_PATH_ENV)
    if model_path:
        return mlflow.lightgbm.load_model(model_path)
    mlflow.set_tracking_uri(config.MLFLOW_TRACKING_URI)
    return mlflow.lightgbm.load_model(f"models:/{config.MODEL_NAME}@champion")


def champion_version() -> str:
    model_path = os.getenv(MODEL_PATH_ENV)
    if model_path:
        version_file = Path(model_path) / "champion_version.txt"
        return version_file.read_text().strip() if version_file.exists() else "unknown"
    mlflow.set_tracking_uri(config.MLFLOW_TRACKING_URI)
    client = mlflow.MlflowClient()
    return client.get_model_version_by_alias(config.MODEL_NAME, "champion").version