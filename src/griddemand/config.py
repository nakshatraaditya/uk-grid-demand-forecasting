from __future__ import annotations
import os
from pathlib import Path

PROJECT_ROOT = Path(os.getenv("GRIDDEMAND_ROOT", Path(__file__).resolve().parents[2]))
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", f"sqlite:///{PROJECT_ROOT / 'mlflow.db'}")
MLFLOW_EXPERIMENT = "grid-demand-forecast"
MODEL_NAME = "griddemand-lgbm"


NESO_API_BASE = "https://api.neso.energy/api/3/action"
NESO_DEMAND_RESOURCE_ID = os.getenv(
    "NESO_DEMAND_RESOURCE_ID", "177f6fa4-ae49-4182-81ea-0c6b35f26ca6"
)

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


UK_CITIES: dict[str, dict] = {
    "london":     {"lat": 51.51, "lon": -0.13, "population": 9_000_000},
    "birmingham": {"lat": 52.48, "lon": -1.90, "population": 3_030_000},
    "manchester": {"lat": 53.48, "lon": -2.24, "population": 3_010_000},
    "leeds":      {"lat": 53.80, "lon": -1.55, "population": 2_400_000},
    "glasgow":    {"lat": 55.86, "lon": -4.25, "population": 1_860_000},
}


_TOTAL_POP = sum(c["population"] for c in UK_CITIES.values())
for _city in UK_CITIES.values():
    _city["weight"] = _city["population"] / _TOTAL_POP

WEATHER_VARS = ["temperature_2m", "wind_speed_10m", "cloud_cover"]


REQUEST_TIMEOUT = 30  
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0  