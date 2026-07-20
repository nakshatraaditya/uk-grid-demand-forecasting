from __future__ import annotations
import numpy as np
import pandas as pd
from griddemand import config
from griddemand.features.build import add_features
from griddemand.models.train import run_training, three_way_split, train_and_evaluate


def synthetic_features(days: int = 28) -> pd.DataFrame:
    n = days * 48
    ts = pd.date_range("2026-01-01", periods=n, freq="30min", tz="UTC")
    t = np.arange(n)
    rng = np.random.default_rng(7)
    demand = (
        30000
        + 8000 * np.sin(2 * np.pi * t / 48)
        + 1500 * np.sin(2 * np.pi * t / 336)
        + rng.normal(0, 400, n)
    )
    df = pd.DataFrame(
        {
            "ts_utc": ts,
            "nd_mw": demand,
            "tsd_mw": demand + 1000,
            "temperature_2m": 10 + 5 * np.sin(2 * np.pi * t / 48),
            "wind_speed_10m": 12.0,
            "cloud_cover": 60.0,
        }
    )
    return add_features(df)


FAST_PARAMS = {"learning_rate": 0.2}


class TestSplit:
    def test_three_way_split_is_chronological(self):
        df = synthetic_features()
        train, valid, test = three_way_split(df)
        assert train.ts_utc.max() < valid.ts_utc.min() < test.ts_utc.max()
        assert len(train) + len(valid) + len(test) == len(df)


class TestTraining:
    def test_train_produces_finite_metrics(self):
        model, metrics, test = train_and_evaluate(
            synthetic_features(), FAST_PARAMS, num_boost_round=50, early_stopping_rounds=10
        )
        assert np.isfinite(metrics["model_mape_pct"])
        assert metrics["model_mape_pct"] > 0
        assert len(test) > 0 and test["pred"].notna().all()

    def test_model_beats_baseline_on_learnable_series(self):
        _, metrics, _ = train_and_evaluate(
            synthetic_features(), FAST_PARAMS, num_boost_round=200, early_stopping_rounds=25
        )
        assert metrics["model_mape_pct"] < metrics["daily_naive_mape_pct"]


class TestTrackedRun:
    def test_run_training_logs_and_promotes(self, tmp_path, monkeypatch):
        
        monkeypatch.setattr(
            config, "MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path / 'mlflow.db'}"
        )
        monkeypatch.chdir(tmp_path)  
        result = run_training(synthetic_features(), FAST_PARAMS)
        assert result["run_id"]
        assert result["promoted"] is True  # learnable series must pass the gate

        from griddemand.models.registry import load_champion

        model = load_champion()
        assert model.num_trees() > 0