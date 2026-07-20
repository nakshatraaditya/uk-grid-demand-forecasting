from __future__ import annotations
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from griddemand import config
from griddemand.features.build import add_features
from griddemand.models.train import run_training

VALID_ROW = {
    "lag_48": 30000, "lag_96": 31000, "lag_336": 29500,
    "roll_mean_48": 30500, "roll_max_48": 38000, "roll_min_48": 22000,
    "hour": 18.0, "day_of_week": 2, "is_weekend": 0, "month": 7,
    "hour_sin": -1.0, "hour_cos": 0.0,
    "temperature_2m": 19.5, "wind_speed_10m": 14.0, "cloud_cover": 40.0,
}


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("mlflow_api")
    original_uri = config.MLFLOW_TRACKING_URI
    config.MLFLOW_TRACKING_URI = f"sqlite:///{tmp / 'mlflow.db'}"

    import os

    cwd = os.getcwd()
    os.chdir(tmp)  
    n = 28 * 48
    ts = pd.date_range("2026-01-01", periods=n, freq="30min", tz="UTC")
    t = np.arange(n)
    demand = 30000 + 8000 * np.sin(2 * np.pi * t / 48) + np.random.default_rng(3).normal(0, 400, n)
    df = add_features(
        pd.DataFrame(
            {
                "ts_utc": ts, "nd_mw": demand, "tsd_mw": demand + 1000,
                "temperature_2m": 15.0, "wind_speed_10m": 10.0, "cloud_cover": 50.0,
            }
        )
    )
    run_training(df, {"learning_rate": 0.2})

    from griddemand.serving.app import app

    with TestClient(app) as c:
        yield c

    os.chdir(cwd)
    config.MLFLOW_TRACKING_URI = original_uri


class TestHealth:
    def test_health_reports_model_loaded(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok", "model_loaded": True}


class TestPredict:
    def test_valid_request_returns_plausible_forecast(self, client):
        r = client.post("/predict", json={"rows": [VALID_ROW]})
        assert r.status_code == 200
        body = r.json()
        assert body["n"] == 1
        assert body["model_version"] == "1"
        assert 15000 < body["predictions_mw"][0] < 45000

    def test_batch_request(self, client):
        r = client.post("/predict", json={"rows": [VALID_ROW] * 48})
        assert r.status_code == 200
        assert r.json()["n"] == 48

    def test_out_of_range_hour_rejected_with_422(self, client):
        bad = {**VALID_ROW, "hour": 27.0}  # no such hour
        r = client.post("/predict", json={"rows": [bad]})
        assert r.status_code == 422
        assert "hour" in str(r.json())

    def test_missing_field_rejected_with_422(self, client):
        bad = {k: v for k, v in VALID_ROW.items() if k != "lag_48"}
        r = client.post("/predict", json={"rows": [bad]})
        assert r.status_code == 422

    def test_negative_demand_lag_rejected_with_422(self, client):
        bad = {**VALID_ROW, "lag_48": -100}
        r = client.post("/predict", json={"rows": [bad]})
        assert r.status_code == 422

    def test_empty_rows_rejected_with_422(self, client):
        r = client.post("/predict", json={"rows": []})
        assert r.status_code == 422