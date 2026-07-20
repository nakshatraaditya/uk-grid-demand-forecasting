from __future__ import annotations
import numpy as np
import pandas as pd
import pytest
from griddemand.features.build import HORIZON, TARGET, add_features
from griddemand.models.baseline import chronological_split, evaluate, seasonal_naive_report


def synthetic_frame(days: int = 21) -> pd.DataFrame:
    n = days * 48
    ts = pd.date_range("2026-01-01", periods=n, freq="30min", tz="UTC")
    t = np.arange(n)
    demand = 30000 + 8000 * np.sin(2 * np.pi * t / 48) + np.random.default_rng(0).normal(0, 300, n)
    return pd.DataFrame(
        {
            "ts_utc": ts,
            TARGET: demand,
            "tsd_mw": demand + 1000,
            "temperature_2m": 10 + 5 * np.sin(2 * np.pi * t / 48),
            "wind_speed_10m": 12.0,
            "cloud_cover": 60.0,
        }
    )


class TestLeakage:
    def test_lag_features_only_use_past_beyond_horizon(self):
        df = add_features(synthetic_frame())
        raw = synthetic_frame().set_index("ts_utc")[TARGET]
        for col in ["lag_48", "lag_96", "lag_336", "roll_mean_48"]:
            for i in [0, len(df) // 2, len(df) - 1]:
                t = df.ts_utc.iloc[i]
                cutoff = t - pd.Timedelta(minutes=30 * HORIZON)
                past = raw.loc[:cutoff]
                assert df[col].iloc[i] <= past.max() + 1e-6, f"{col} leaks future data"
    
    def test_lags_stay_time_correct_across_data_gaps(self):
        df = synthetic_frame(days=21)
        gap_start = pd.Timestamp("2026-01-08", tz="UTC")
        gap_end = pd.Timestamp("2026-01-11", tz="UTC")
        gapped = df[(df.ts_utc < gap_start) | (df.ts_utc >= gap_end)]

        out = add_features(gapped)
        raw = df.set_index("ts_utc")[TARGET]
        t = pd.Timestamp("2026-01-19 12:00", tz="UTC")
        row = out[out.ts_utc == t]
        assert row.lag_48.iloc[0] == pytest.approx(raw.loc[t - pd.Timedelta(days=1)])

    def test_lag_48_is_exactly_yesterday_same_period(self):
        df = add_features(synthetic_frame())
        raw = synthetic_frame()
        merged = df.merge(
            raw[["ts_utc", TARGET]].assign(ts_utc=lambda x: x.ts_utc + pd.Timedelta(days=1)),
            on="ts_utc",
            suffixes=("", "_yesterday"),
        )
        pd.testing.assert_series_equal(
            merged["lag_48"], merged[f"{TARGET}_yesterday"],
            check_names=False,
        )


class TestCalendar:
    def test_hour_is_local_wall_clock_in_summer(self):
        df = synthetic_frame(days=30)
        df["ts_utc"] = pd.date_range("2026-07-01", periods=len(df), freq="30min", tz="UTC")
        out = add_features(df)
        row = out[out.ts_utc == pd.Timestamp("2026-07-10 23:00", tz="UTC")]
        assert row.hour.iloc[0] == 0.0

    def test_weekend_flag(self):
        df = add_features(synthetic_frame())
        local = df.ts_utc.dt.tz_convert("Europe/London")
        assert (df.is_weekend == (local.dt.dayofweek >= 5).astype(int)).all()


class TestBaseline:
    def test_perfectly_periodic_series_gives_zero_daily_naive_error(self):
        n = 21 * 48
        ts = pd.date_range("2026-01-01", periods=n, freq="30min", tz="UTC")
        t = np.arange(n)
        df = pd.DataFrame(
            {
                "ts_utc": ts,
                TARGET: 30000 + 8000 * np.sin(2 * np.pi * t / 48),  # no noise
                "temperature_2m": 10.0, "wind_speed_10m": 12.0, "cloud_cover": 60.0,
            }
        )
        report = seasonal_naive_report(add_features(df))
        daily = report[report.model == "daily_naive"].iloc[0]
        assert daily.mape_pct == pytest.approx(0.0, abs=1e-9)

    def test_chronological_split_does_not_shuffle(self):
        df = add_features(synthetic_frame())
        train, test = chronological_split(df, test_frac=0.2)
        assert train.ts_utc.max() < test.ts_utc.min()

    def test_evaluate_metrics(self):
        y = pd.Series([100.0, 200.0])
        yhat = pd.Series([110.0, 180.0])
        m = evaluate(y, yhat)
        assert m["mae_mw"] == pytest.approx(15.0)
        assert m["mape_pct"] == pytest.approx((0.10 + 0.10) / 2 * 100)