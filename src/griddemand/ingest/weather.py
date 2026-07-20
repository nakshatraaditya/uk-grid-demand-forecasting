from __future__ import annotations
import logging
from datetime import date
import pandas as pd
from griddemand import config
from griddemand.http import get_json

logger = logging.getLogger(__name__)


def fetch_city_weather(
    city: str, start: date, end: date, endpoint: str = "archive"
) -> pd.DataFrame:
    meta = config.UK_CITIES[city]
    url = (
        config.OPEN_METEO_ARCHIVE_URL
        if endpoint == "archive"
        else config.OPEN_METEO_FORECAST_URL
    )
    params = {
        "latitude": meta["lat"],
        "longitude": meta["lon"],
        "hourly": ",".join(config.WEATHER_VARS),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "timezone": "UTC",  # keep everything UTC; convert at the edges only
    }
    payload = get_json(url, params=params)
    hourly = payload["hourly"]
    df = pd.DataFrame(hourly)
    df["ts_utc"] = pd.to_datetime(df.pop("time"), utc=True)
    df["city"] = city
    return df


def weighted_national_weather(city_frames: list[pd.DataFrame]) -> pd.DataFrame:
    df = pd.concat(city_frames, ignore_index=True)
    df["weight"] = df["city"].map({c: m["weight"] for c, m in config.UK_CITIES.items()})

    def wavg(group: pd.DataFrame) -> pd.Series:
        w = group["weight"]
        return pd.Series(
            {var: (group[var] * w).sum() / w.sum() for var in config.WEATHER_VARS}
        )

    national = df.groupby("ts_utc").apply(wavg, include_groups=False).reset_index()
    return national.sort_values("ts_utc").reset_index(drop=True)


def fetch_national_weather(start: date, end: date, endpoint: str = "archive") -> pd.DataFrame:
    frames = [fetch_city_weather(c, start, end, endpoint) for c in config.UK_CITIES]
    return weighted_national_weather(frames)


def ingest_weather(start: date, end: date, endpoint: str = "archive") -> pd.DataFrame:
    national = fetch_national_weather(start, end, endpoint)

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.PROCESSED_DIR / "weather.parquet"
    national.to_parquet(out_path, index=False)
    logger.info("Wrote %d national weather rows → %s", len(national), out_path)
    return national