from __future__ import annotations
import lightgbm as lgb
import mlflow
from griddemand import config

def load_champion() -> lgb.Booster:
    mlflow.set_tracking_uri(config.MLFLOW_TRACKING_URI)
    return mlflow.lightgbm.load_model(f"models:/{config.MODEL_NAME}@champion")


def champion_version() -> str:
    mlflow.set_tracking_uri(config.MLFLOW_TRACKING_URI)
    client = mlflow.MlflowClient()
    return client.get_model_version_by_alias(config.MODEL_NAME, "champion").version