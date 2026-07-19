from __future__ import annotations
import logging
from datetime import date
import pandas as pd
from griddemand import config
from griddemand.http import get_json

logger = logging.getLogger(__name__)
MIN_PLAUSIBLE_ND_MW = 5000

def fetch_demand_raw(start: date, end: date) -> list[dict]:
    sql = (
        f'SELECT "SETTLEMENT_DATE", "SETTLEMENT_PERIOD", "ND", "TSD" '
        f'FROM "{config.NESO_DEMAND_RESOURCE_ID}" '
        f"WHERE \"SETTLEMENT_DATE\" >= '{start.isoformat()}' "
        f"AND \"SETTLEMENT_DATE\" <= '{end.isoformat()}' "
        f'ORDER BY "SETTLEMENT_DATE", "SETTLEMENT_PERIOD"'
    )
    payload = get_json(f"{config.NESO_API_BASE}/datastore_search_sql", params={"sql": sql})
    if not payload.get("success"):
        raise RuntimeError(f"NESO API returned success=false: {payload}")
    records = payload["result"]["records"]
    logger.info("Fetched %d demand rows from NESO (%s → %s)", len(records), start, end)
    return records


def demand_to_frame(records: list[dict]) -> pd.DataFrame:
    if not records:
        raise ValueError("No demand records to process")

    df = pd.DataFrame(records)
    df.columns = [c.lower() for c in df.columns]

    df["settlement_date"] = pd.to_datetime(df["settlement_date"]).dt.tz_localize(None)
    df["settlement_period"] = df["settlement_period"].astype(int)
    df["nd_mw"] = pd.to_numeric(df["nd"], errors="coerce")
    df["tsd_mw"] = pd.to_numeric(df["tsd"], errors="coerce")

    local_midnight = df["settlement_date"].dt.tz_localize(
        "Europe/London", ambiguous="NaT", nonexistent="shift_forward"
    )
    midnight_utc = local_midnight.dt.tz_convert("UTC")
    offset = pd.to_timedelta((df["settlement_period"] - 1) * 30, unit="m")
    df["ts_utc"] = midnight_utc + offset

    out = (
        df[["ts_utc", "nd_mw", "tsd_mw"]]
        .dropna(subset=["ts_utc", "nd_mw"])
        .sort_values("ts_utc")
        .drop_duplicates(subset="ts_utc", keep="last")
        .reset_index(drop=True)
    )
    n_bad = int((out["nd_mw"] < MIN_PLAUSIBLE_ND_MW).sum())
    if n_bad:
        logger.warning(
            "Dropping %d rows with implausible ND < %d MW (NESO placeholder rows)",
            n_bad, MIN_PLAUSIBLE_ND_MW,
        )
        out = out[out["nd_mw"] >= MIN_PLAUSIBLE_ND_MW].reset_index(drop=True)
    return out


def ingest_demand(start: date, end: date) -> pd.DataFrame:
    records = fetch_demand_raw(start, end)
    df = demand_to_frame(records)

    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = config.RAW_DIR / f"demand_{start.isoformat()}_{end.isoformat()}.parquet"
    pd.DataFrame(records).to_parquet(raw_path, index=False)

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    clean_path = config.PROCESSED_DIR / "demand.parquet"
    df.to_parquet(clean_path, index=False)
    logger.info("Wrote %d clean demand rows → %s", len(df), clean_path)
    return df