from __future__ import annotations
import numpy as np
import pandas as pd
import mlflow
import pytest
from griddemand import config
from griddemand.features.build import FEATURE_COLS, add_features
from griddemand.models.train import run_training


@pytest.fixture()
def promoted_champion(tmp_path, monkeypatch):
    monkeypatch.setattr(
        config, "MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path / 'mlflow.db'}"
    )
    monkeypatch.chdir(tmp_path)

    n = 28 * 48
    ts = pd.date_range("2026-01-01", periods=n, freq="30min", tz="UTC")
    t = np.arange(n)
    demand = 30000 + 8000 * np.sin(2 * np.pi * t / 48) + np.random.default_rng(5).normal(0, 400, n)
    df = add_features(
        pd.DataFrame(
            {
                "ts_utc": ts, "nd_mw": demand, "tsd_mw": demand + 1000,
                "temperature_2m": 15.0, "wind_speed_10m": 10.0, "cloud_cover": 50.0,
            }
        )
    )
    run_training(df, {"learning_rate": 0.2})
    return tmp_path


def test_export_then_load_from_path(promoted_champion, monkeypatch):
    from griddemand.models.registry import champion_version, load_champion

    export_dir = promoted_champion / "model_export"
    model = load_champion()
    version = champion_version()
    mlflow.lightgbm.save_model(model, path=str(export_dir))
    (export_dir / "champion_version.txt").write_text(str(version))

    monkeypatch.setenv("GRIDDEMAND_MODEL_PATH", str(export_dir))
    monkeypatch.setattr(config, "MLFLOW_TRACKING_URI", "sqlite:///nonexistent/broken.db")

    loaded = load_champion()
    assert champion_version() == "1"

    row = pd.DataFrame(
        [dict(zip(FEATURE_COLS, [30000, 31000, 29500, 30500, 38000, 22000,
                                 18.0, 2, 0, 7, -1.0, 0.0, 15.0, 10.0, 50.0]))]
    )
    assert loaded.predict(row)[0] == pytest.approx(model.predict(row)[0])