from __future__ import annotations
import pandas as pd
import pytest
from griddemand.ingest import neso
from griddemand.ingest.store import upsert_parquet

class TestDiscovery:
    PAYLOAD = {
        "success": True,
        "result": {
            "resources": [
                {"id": "faq-id", "name": "Frequently Asked Questions (FAQ)"},
                {"id": "id-2022", "name": "Historic Demand Data 2022"},
                {"id": "id-2023", "name": "Historic Demand Data 2023"},
            ]
        },
    }

    def test_matches_resource_by_year_name(self, monkeypatch):
        monkeypatch.setattr(neso, "get_json", lambda url, params=None: self.PAYLOAD)
        assert neso.discover_demand_resource(2023) == "id-2023"
        assert neso.discover_demand_resource(2022) == "id-2022"

    def test_missing_year_raises(self, monkeypatch):
        monkeypatch.setattr(neso, "get_json", lambda url, params=None: self.PAYLOAD)
        with pytest.raises(RuntimeError, match="2019"):
            neso.discover_demand_resource(2019)

class TestUpsert:
    def make_frame(self, start: str, periods: int, value: float) -> pd.DataFrame:
        ts = pd.date_range(start, periods=periods, freq="30min", tz="UTC")
        return pd.DataFrame({"ts_utc": ts, "nd_mw": value})

    def test_creates_new_file(self, tmp_path):
        path = tmp_path / "demand.parquet"
        out = upsert_parquet(self.make_frame("2024-01-01", 48, 30000.0), path)
        assert path.exists() and len(out) == 48

    def test_merges_disjoint_ranges(self, tmp_path):
        path = tmp_path / "demand.parquet"
        upsert_parquet(self.make_frame("2024-01-01", 48, 30000.0), path)
        out = upsert_parquet(self.make_frame("2024-01-02", 48, 31000.0), path)
        assert len(out) == 96
        assert out.ts_utc.is_monotonic_increasing

    def test_rerun_is_idempotent_and_newest_wins(self, tmp_path):
        path = tmp_path / "demand.parquet"
        upsert_parquet(self.make_frame("2024-01-01", 48, 30000.0), path)
        out = upsert_parquet(self.make_frame("2024-01-01", 48, 29000.0), path)
        assert len(out) == 48
        assert (out.nd_mw == 29000.0).all()