from __future__ import annotations
import pandas as pd
import pytest
from griddemand.ingest.neso import demand_to_frame
from griddemand.ingest.weather import weighted_national_weather


def make_neso_records(day: str, n_periods: int = 48) -> list[dict]:
    return [
        {
            "SETTLEMENT_DATE": day,
            "SETTLEMENT_PERIOD": p,
            "ND": 25000 + 100 * p,
            "TSD": 26000 + 100 * p,
        }
        for p in range(1, n_periods + 1)
    ]


class TestDemandToFrame:
    def test_winter_day_period1_is_midnight_utc(self):
        # January: UK local time == UTC, so period 1 starts 00:00 UTC.
        df = demand_to_frame(make_neso_records("2026-01-15"))
        assert df.ts_utc.iloc[0] == pd.Timestamp("2026-01-15 00:00", tz="UTC")
        assert len(df) == 48

    def test_summer_day_period1_is_2300_utc_previous_day(self):
        # July: UK is on BST (UTC+1). Local midnight = 23:00 UTC the day before.
        # This is THE classic timezone bug in UK energy data — the test pins it.
        df = demand_to_frame(make_neso_records("2026-07-15"))
        assert df.ts_utc.iloc[0] == pd.Timestamp("2026-07-14 23:00", tz="UTC")

    def test_half_hourly_spacing(self):
        df = demand_to_frame(make_neso_records("2026-01-15"))
        deltas = df.ts_utc.diff().dropna().unique()
        assert list(deltas) == [pd.Timedelta(minutes=30)]

    def test_short_dst_day_has_46_periods(self):
        # Clocks go forward 29 Mar 2026: the day has 23 hours = 46 periods.
        df = demand_to_frame(make_neso_records("2026-03-29", n_periods=46))
        assert len(df) == 46
        # Period 46 starts at UTC midnight + 45*30min = 22:30 UTC and ends at
        # 23:00 UTC — which IS the next local midnight (00:00 BST, 30 Mar).
        assert df.ts_utc.iloc[-1] == pd.Timestamp("2026-03-29 22:30", tz="UTC")

    def test_deduplicates_and_sorts(self):
        records = make_neso_records("2026-01-15") + make_neso_records("2026-01-15")
        df = demand_to_frame(records)
        assert len(df) == 48
        assert df.ts_utc.is_monotonic_increasing

    def test_empty_records_raise(self):
        with pytest.raises(ValueError):
            demand_to_frame([])

    def test_drops_placeholder_zero_demand_rows(self):
        records = make_neso_records("2026-01-15")
        records[10]["ND"] = 0
        records[20]["ND"] = 0
        df = demand_to_frame(records)
        assert len(df) == 46
        assert (df.nd_mw >= 5000).all()


class TestWeightedWeather:
    def test_population_weighting(self):
        from griddemand import config

        w_lon = config.UK_CITIES["london"]["weight"]
        w_bham = config.UK_CITIES["birmingham"]["weight"]

        ts = pd.to_datetime(["2026-01-15 00:00"], utc=True)
        lon = pd.DataFrame(
            {"ts_utc": ts, "temperature_2m": [10.0], "wind_speed_10m": [5.0],
             "cloud_cover": [50.0], "city": "london"}
        )
        bham = pd.DataFrame(
            {"ts_utc": ts, "temperature_2m": [0.0], "wind_speed_10m": [10.0],
             "cloud_cover": [100.0], "city": "birmingham"}
        )
        out = weighted_national_weather([lon, bham])
        expected_temp = (10.0 * w_lon + 0.0 * w_bham) / (w_lon + w_bham)
        assert out.temperature_2m.iloc[0] == pytest.approx(expected_temp)
        assert len(out) == 1

    def test_weights_sum_to_one(self):
        from griddemand import config

        total = sum(c["weight"] for c in config.UK_CITIES.values())
        assert total == pytest.approx(1.0)