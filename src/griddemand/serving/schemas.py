from __future__ import annotations
from pydantic import BaseModel, Field


class FeatureVector(BaseModel):
    lag_48: float = Field(gt=0, description="Demand (MW) same period yesterday")
    lag_96: float = Field(gt=0, description="Demand (MW) same period 2 days ago")
    lag_336: float = Field(gt=0, description="Demand (MW) same period last week")
    roll_mean_48: float = Field(gt=0, description="Yesterday's mean demand (MW)")
    roll_max_48: float = Field(gt=0, description="Yesterday's max demand (MW)")
    roll_min_48: float = Field(gt=0, description="Yesterday's min demand (MW)")
    hour: float = Field(ge=0, lt=24, description="Local wall-clock hour (0-23.5)")
    day_of_week: int = Field(ge=0, le=6, description="0=Monday .. 6=Sunday")
    is_weekend: int = Field(ge=0, le=1)
    month: int = Field(ge=1, le=12)
    hour_sin: float = Field(ge=-1, le=1)
    hour_cos: float = Field(ge=-1, le=1)
    temperature_2m: float = Field(gt=-30, lt=45, description="National weighted °C")
    wind_speed_10m: float = Field(ge=0, lt=200, description="km/h")
    cloud_cover: float = Field(ge=0, le=100, description="%")


class PredictRequest(BaseModel):
    rows: list[FeatureVector] = Field(min_length=1, max_length=96)


class PredictResponse(BaseModel):
    predictions_mw: list[float]
    n: int
    model_name: str
    model_version: str


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool