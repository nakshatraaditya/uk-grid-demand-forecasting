from __future__ import annotations
import argparse
import logging
from datetime import date, timedelta
from griddemand import config
from griddemand.ingest.neso import demand_to_frame, discover_demand_resource, fetch_demand_year
from griddemand.ingest.store import upsert_parquet
from griddemand.ingest.weather import fetch_national_weather

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("backfill")


def backfill_year(year: int) -> None:
    start, end = date(year, 1, 1), date(year, 12, 31)

    resource_id = discover_demand_resource(year)
    records = fetch_demand_year(resource_id)
    demand = demand_to_frame(records)
    upsert_parquet(demand, config.PROCESSED_DIR / "demand.parquet")

    # Archive endpoint can't serve the future (or the last ~week).
    weather_end = min(end, date.today() - timedelta(days=7))
    n_weather = 0
    if weather_end >= start:
        weather = fetch_national_weather(start, weather_end, endpoint="archive")
        upsert_parquet(weather, config.PROCESSED_DIR / "weather.parquet")
        n_weather = len(weather)

    logger.info(
        "Year %d done: %d demand rows, %d weather rows", year, len(demand), n_weather
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill historic demand + weather")
    parser.add_argument(
        "--years", type=int, nargs="+", required=True, help="e.g. --years 2022 2023 2024"
    )
    args = parser.parse_args()

    failed = []
    for year in sorted(args.years):
        try:
            backfill_year(year)
        except Exception:
            logger.exception("Year %d FAILED — continuing with the rest", year)
            failed.append(year)

    if failed:
        print(f"\nDone with failures: {failed} — re-run just those years")
    else:
        print("\nAll years backfilled. Next:")
        print("  python scripts/build_features.py")
        print("  python scripts/train.py")


if __name__ == "__main__":
    main()