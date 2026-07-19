# UK Grid Demand Forecasting — Full MLOps Loop

Forecasts UK national electricity demand (half-hourly) from live NESO grid data
and population-weighted weather, with experiment tracking, containerized
serving, CI/CD, and drift-triggered retraining.

**Status: Phase 1 — data ingestion** (of 7 phases)

## Data sources (free, keyless)
- **NESO Demand Data Update** — half-hourly national demand (ND/TSD), updated daily
- **Open-Meteo** — hourly weather for 5 UK metros, population-weighted into a national series

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Run

```bash
# Pull 90 days of demand + weather (writes data/raw + data/processed)
python scripts/ingest.py --days 90

# Test suite (fully offline — no network needed)
pytest -v
```

If the NESO pull fails, the resource ID may have rotated — grab the current one
from https://www.neso.energy/data-portal/demand-data-update and set
`NESO_DEMAND_RESOURCE_ID`.

## Project layout

```
src/griddemand/
├── config.py          # all knobs in one place, env-overridable
├── http.py            # retry/backoff/timeout wrapper — no bare requests.get
└── ingest/
    ├── neso.py        # demand: settlement periods → UTC timestamps (DST-safe)
    └── weather.py     # 5-city population-weighted national weather
scripts/ingest.py      # thin CLI orchestrator
tests/                 # offline, fixture-based — CI never hits a live API
```

## Design decisions worth knowing
- **raw vs processed data**: raw API responses are persisted untouched
  (audit/replay), transformations always run on a copy.
- **Everything UTC internally**: UK settlement periods count from *local*
  midnight, so DST days have 46/50 periods. Timestamps are derived as
  local-midnight → UTC + elapsed offset, which the test suite pins down.
- **Population-weighted weather**: national demand responds to weather where
  people live; one city is a noisy proxy.