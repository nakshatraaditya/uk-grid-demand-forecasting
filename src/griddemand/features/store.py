"""Minimal offline feature store.

A production feature store (Feast, Tecton) tracks online + offline parity, TTLs,
point-in-time joins, and materialisation jobs. Overkill for a batch, single-
publisher pipeline like this one, but the *offline* half — versioned, hashable
feature snapshots you can reproduce a run from — is worth having on its own.

This module writes each build of the feature table as a Parquet snapshot named
by a short content hash, alongside a `_manifest.jsonl` that records: when it
was written, the schema (columns + dtypes), the row count, the time range it
covers, the git SHA in effect, and the hash. Reads happen by hash or by
"latest".

Why not Feast for this project
------------------------------
- Single publisher, one consumer, no online serving of raw features (the
  model is served, not the feature vectors).
- No online/offline skew risk to hedge against — training and inference both
  use the same `build_features` code.
- Feast adds an infra dependency (Redis / DynamoDB / a registry service) and a
  concept surface that would be out of proportion with the workload.

If any of those change (multiple consumers, online lookup, cross-team
governance), this module has enough shape to be replaced by Feast without
rewriting callers: `write(df)` and `read(version="latest")` are the only two
functions in use.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from griddemand import config
from griddemand.features.build import FEATURE_COLS, TARGET

logger = logging.getLogger(__name__)

STORE_DIR = config.PROCESSED_DIR / "feature_store"
MANIFEST = STORE_DIR / "_manifest.jsonl"
TIMESTAMP_COL = "settlement_datetime_utc"


@dataclass(frozen=True)
class FeatureVersion:
    """Row in `_manifest.jsonl` — one per snapshot."""
    version: str            # 12-char content hash, e.g. "a1b2c3d4e5f6"
    created_at_utc: str     # ISO-8601 UTC timestamp
    rows: int
    columns: list[str]
    dtypes: dict[str, str]
    time_from_utc: str | None
    time_to_utc: str | None
    git_sha: str | None
    path: str               # repo-relative Parquet path


def _short_hash(df: pd.DataFrame) -> str:
    """Deterministic 12-char content hash of the feature table."""
    payload = pd.util.hash_pandas_object(df, index=True).values.tobytes()
    payload += ",".join(df.columns).encode() + str(df.dtypes.to_dict()).encode()
    return hashlib.sha256(payload).hexdigest()[:12]


def _git_sha() -> str | None:
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=config.PROJECT_ROOT, stderr=subprocess.DEVNULL, text=True,
        ).strip()
        return sha or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _time_range(df: pd.DataFrame) -> tuple[str | None, str | None]:
    if TIMESTAMP_COL not in df.columns:
        return None, None
    ts = pd.to_datetime(df[TIMESTAMP_COL], utc=True)
    if ts.empty:
        return None, None
    return ts.min().isoformat(), ts.max().isoformat()


def _validate(df: pd.DataFrame) -> None:
    """Fail loudly if a caller forgets the feature contract."""
    missing = [c for c in FEATURE_COLS + [TARGET] if c not in df.columns]
    if missing:
        raise ValueError(f"feature store: dataframe missing columns {missing}")
    if df[FEATURE_COLS].isna().any().any():
        # Lags/rolls are dropped in build.add_features; anything past that is
        # a leakage or a plumbing bug.
        raise ValueError("feature store: NaNs found in FEATURE_COLS — check add_features()")
    if len(df) == 0:
        raise ValueError("feature store: refusing to snapshot an empty frame")


def _read_manifest() -> list[FeatureVersion]:
    if not MANIFEST.exists():
        return []
    with MANIFEST.open() as fh:
        return [FeatureVersion(**json.loads(line)) for line in fh if line.strip()]


def _append_manifest(v: FeatureVersion) -> None:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("a") as fh:
        fh.write(json.dumps(asdict(v)) + "\n")


def write(df: pd.DataFrame) -> FeatureVersion:
    """Snapshot a feature table.

    Returns the FeatureVersion (its ``version`` is the content hash you pass
    back to :func:`read`). Idempotent: writing the same frame twice returns
    the existing version and does not duplicate the file.
    """
    _validate(df)
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    version = _short_hash(df)
    path = STORE_DIR / f"{version}.parquet"
    rel_path = str(path.relative_to(config.PROJECT_ROOT))

    existing = {v.version: v for v in _read_manifest()}
    if version in existing:
        logger.info("feature store: %s already present, skipping write", version)
        return existing[version]

    df.to_parquet(path, index=False)
    t_from, t_to = _time_range(df)
    v = FeatureVersion(
        version=version,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        rows=len(df),
        columns=list(df.columns),
        dtypes={c: str(t) for c, t in df.dtypes.items()},
        time_from_utc=t_from,
        time_to_utc=t_to,
        git_sha=_git_sha(),
        path=rel_path,
    )
    _append_manifest(v)
    logger.info("feature store: wrote %s (%d rows) → %s", version, len(df), rel_path)
    return v


def read(version: str = "latest") -> pd.DataFrame:
    """Load a snapshot by content hash. ``"latest"`` picks the last entry."""
    versions = _read_manifest()
    if not versions:
        raise FileNotFoundError(f"feature store empty: {MANIFEST} not found")
    if version == "latest":
        v = versions[-1]
    else:
        matches = [x for x in versions if x.version == version]
        if not matches:
            raise KeyError(f"feature store: no snapshot with version {version!r}")
        v = matches[0]
    return pd.read_parquet(config.PROJECT_ROOT / v.path)


def list_versions() -> Iterable[FeatureVersion]:
    return _read_manifest()
