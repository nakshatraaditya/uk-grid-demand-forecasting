from __future__ import annotations
import numpy as np
import pandas as pd
from griddemand.features.build import add_features
from griddemand.monitoring.drift import (
    DRIFT_SHARE_THRESHOLD,
    drift_summary,
    should_retrain,
)


def make_features(days: int = 28, temp_shift: float = 0.0, seed: int = 0) -> pd.DataFrame:
    n = days * 48
    ts = pd.date_range("2026-01-01", periods=n, freq="30min", tz="UTC")
    t = np.arange(n)
    rng = np.random.default_rng(seed)
    demand = 30000 + 8000 * np.sin(2 * np.pi * t / 48) + rng.normal(0, 400, n)
    return add_features(
        pd.DataFrame(
            {
                "ts_utc": ts,
                "nd_mw": demand,
                "tsd_mw": demand + 1000,
                "temperature_2m": 15 + temp_shift + rng.normal(0, 2, n),
                "wind_speed_10m": np.clip(10 + rng.normal(0, 3, n), 0, None),
                "cloud_cover": np.clip(50 + rng.normal(0, 20, n), 0, 100),
            }
        )
    )


class TestDriftDetection:
    def test_same_distribution_low_drift(self):
        ref = make_features(seed=1)
        cur = make_features(seed=2)  # new sample, same process
        summary, _ = drift_summary(ref, cur)
        assert summary["drift_share"] <= DRIFT_SHARE_THRESHOLD

    def test_shifted_temperature_is_detected(self):
        ref = make_features(seed=1)
        cur = make_features(seed=2, temp_shift=10.0)  # +10C regime change
        summary, _ = drift_summary(ref, cur)
        assert summary["columns"]["temperature_2m"]["drifted"] is True


class TestRetrainDecision:
    def test_healthy_system_does_not_retrain(self):
        drift = {"drift_share": 0.1, "n_drifted": 1, "columns": {}}
        perf = {"degraded": False, "current_mape_pct": 5.0, "champion_test_mape_pct": 5.4}
        retrain, reasons = should_retrain(drift, perf)
        assert retrain is False and reasons == []

    def test_drift_alone_triggers(self):
        drift = {"drift_share": 0.5, "n_drifted": 8, "columns": {}}
        perf = {"degraded": False, "current_mape_pct": 5.0, "champion_test_mape_pct": 5.4}
        retrain, reasons = should_retrain(drift, perf)
        assert retrain is True
        assert "data drift" in reasons[0]

    def test_degradation_alone_triggers(self):
        drift = {"drift_share": 0.0, "n_drifted": 0, "columns": {}}
        perf = {"degraded": True, "current_mape_pct": 9.1, "champion_test_mape_pct": 5.4}
        retrain, reasons = should_retrain(drift, perf)
        assert retrain is True
        assert "performance" in reasons[0]

    def test_both_signals_give_both_reasons(self):
        drift = {"drift_share": 0.5, "n_drifted": 8, "columns": {}}
        perf = {"degraded": True, "current_mape_pct": 9.1, "champion_test_mape_pct": 5.4}
        retrain, reasons = should_retrain(drift, perf)
        assert retrain is True and len(reasons) == 2