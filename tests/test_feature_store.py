"""Tests for the offline feature store snapshotting logic."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from griddemand.features import store as fs
from griddemand.features.build import FEATURE_COLS, TARGET


def _make_frame(n: int = 8, offset: int = 0) -> pd.DataFrame:
    ts = pd.date_range("2026-01-01", periods=n, freq="30min", tz="UTC")
    df = pd.DataFrame({fs.TIMESTAMP_COL: ts})
    for i, col in enumerate(FEATURE_COLS):
        df[col] = [float(offset + i + j) for j in range(n)]
    df[TARGET] = [float(offset + 100 + j) for j in range(n)]
    return df


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(fs, "STORE_DIR", tmp_path / "feature_store")
    monkeypatch.setattr(fs, "MANIFEST", tmp_path / "feature_store" / "_manifest.jsonl")
    monkeypatch.setattr(fs.config, "PROJECT_ROOT", tmp_path)
    yield


def test_write_creates_parquet_and_manifest_row():
    v = fs.write(_make_frame())
    assert fs.MANIFEST.exists()
    assert (fs.STORE_DIR / f"{v.version}.parquet").exists()
    lines = fs.MANIFEST.read_text().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["rows"] == 8
    assert row["version"] == v.version
    assert row["time_from_utc"].startswith("2026-01-01")


def test_write_is_idempotent():
    v1 = fs.write(_make_frame())
    v2 = fs.write(_make_frame())
    assert v1.version == v2.version
    assert fs.MANIFEST.read_text().count("\n") == 1


def test_different_frame_yields_different_version():
    v_a = fs.write(_make_frame(offset=0))
    v_b = fs.write(_make_frame(offset=1))
    assert v_a.version != v_b.version
    assert len(list(fs.list_versions())) == 2


def test_read_latest_and_by_hash_roundtrip():
    original = _make_frame()
    v = fs.write(original)
    latest = fs.read("latest")
    by_hash = fs.read(v.version)
    pd.testing.assert_frame_equal(latest, by_hash)
    pd.testing.assert_frame_equal(latest[FEATURE_COLS + [TARGET]],
                                  original[FEATURE_COLS + [TARGET]])


def test_read_missing_version_raises():
    fs.write(_make_frame())
    with pytest.raises(KeyError):
        fs.read("does-not-exist")


def test_write_rejects_missing_feature_column():
    df = _make_frame().drop(columns=["lag_48"])
    with pytest.raises(ValueError, match="missing columns"):
        fs.write(df)


def test_write_rejects_nans_in_features():
    df = _make_frame()
    df.loc[0, "lag_48"] = float("nan")
    with pytest.raises(ValueError, match="NaNs"):
        fs.write(df)


def test_write_rejects_empty_frame():
    df = _make_frame(n=1).iloc[0:0]
    with pytest.raises(ValueError, match="empty"):
        fs.write(df)


def test_read_before_any_write_raises():
    with pytest.raises(FileNotFoundError):
        fs.read()
