from __future__ import annotations
import argparse
import logging
from datetime import date, timedelta
from griddemand.ingest.neso import ingest_demand
from griddemand.ingest.weather import ingest_weather

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest UK demand + weather data")
    parser.add_argument("--days", type=int, default=90, help="Days of history to pull")
    args = parser.parse_args()

    end = date.today() - timedelta(days=1)  # yesterday: today's data is incomplete
    start = end - timedelta(days=args.days)

    demand = ingest_demand(start, end)
    print(f"Demand:  {len(demand)} rows  {demand.ts_utc.min()} -> {demand.ts_utc.max()}")

    # Open-Meteo archive lags ~5 days, so stop the archive pull 6 days back
    archive_end = end - timedelta(days=6)
    weather = ingest_weather(start, archive_end, endpoint="archive")
    print(f"Weather: {len(weather)} rows  {weather.ts_utc.min()} -> {weather.ts_utc.max()}")
    
if __name__ == "__main__":
    main()