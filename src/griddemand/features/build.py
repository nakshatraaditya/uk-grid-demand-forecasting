from __future__ import annotations
import logging
import numpy as np
import pandas as pd
from griddemand import config

logger = logging.getLogger(__name__)

TARGET = "nd_mw"
HORIZON = 48  # half-hourly periods = 1 day ahead


def load_joined() -> pd.DataFrame:
    demand = pd.read_parquet(config.PROCESSED_DIR / "demand.parquet")
    weather = pd.read_parquet(config.PROCESSED_DIR / "weather.parquet")

    weather_hh = (
        weather.set_index("ts_utc")
        .resample("30min")
        .interpolate(method="time")
        .reset_index()
    )
    df = demand.merge(weather_hh, on="ts_utc", how="inner").sort_values("ts_utc")
    logger.info(
        "Joined: %d rows (%s → %s)", len(df), df.ts_utc.min(), df.ts_utc.max()
    )
    return df.reset_index(drop=True)


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for lag in (48, 96, 336):  # yesterday, 2 days ago, last week
        df[f"lag_{lag}"] = df[TARGET].shift(lag)

    shifted = df[TARGET].shift(HORIZON)
    df["roll_mean_48"] = shifted.rolling(48).mean()
    df["roll_max_48"] = shifted.rolling(48).max()
    df["roll_min_48"] = shifted.rolling(48).min()

    local = df["ts_utc"].dt.tz_convert("Europe/London")
    df["hour"] = local.dt.hour + local.dt.minute / 60
    df["day_of_week"] = local.dt.dayofweek
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["month"] = local.dt.month

    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)

    df = df.dropna().reset_index(drop=True)
    return df


FEATURE_COLS = [
    "lag_48", "lag_96", "lag_336",
    "roll_mean_48", "roll_max_48", "roll_min_48",
    "hour", "day_of_week", "is_weekend", "month", "hour_sin", "hour_cos",
    "temperature_2m", "wind_speed_10m", "cloud_cover",
]


def build() -> pd.DataFrame:
    df = add_features(load_joined())
    out_path = config.PROCESSED_DIR / "features.parquet"
    df.to_parquet(out_path, index=False)
    logger.info("Wrote %d feature rows x %d cols → %s", len(df), df.shape[1], out_path)
    return df