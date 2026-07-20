from __future__ import annotations
import numpy as np
import pandas as pd
from griddemand.features.build import add_features
from griddemand.models.train import run_training


def main() -> None:
    n = 28 * 48
    ts = pd.date_range("2026-01-01", periods=n, freq="30min", tz="UTC")
    t = np.arange(n)
    demand = (
        30000
        + 8000 * np.sin(2 * np.pi * t / 48)
        + np.random.default_rng(0).normal(0, 400, n)
    )
    df = add_features(
        pd.DataFrame(
            {
                "ts_utc": ts,
                "nd_mw": demand,
                "tsd_mw": demand + 1000,
                "temperature_2m": 15.0,
                "wind_speed_10m": 10.0,
                "cloud_cover": 50.0,
            }
        )
    )
    result = run_training(df, {"learning_rate": 0.2})
    assert result["promoted"], "CI bootstrap model failed the promotion gate"
    print(f"CI champion ready: run {result['run_id']}")


if __name__ == "__main__":
    main()