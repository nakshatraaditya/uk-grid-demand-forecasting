from __future__ import annotations
import logging
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)


def upsert_parquet(df_new: pd.DataFrame, path: Path, key: str = "ts_utc") -> pd.DataFrame:
    """Merge df_new into the parquet at path, dedup on key (newest wins)."""
    if path.exists():
        existing = pd.read_parquet(path)
        df = pd.concat([existing, df_new], ignore_index=True)
    else:
        df = df_new
    df = (
        df.drop_duplicates(subset=key, keep="last")
        .sort_values(key)
        .reset_index(drop=True)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    logger.info("Upserted %d rows -> %s now has %d rows", len(df_new), path.name, len(df))
    return df