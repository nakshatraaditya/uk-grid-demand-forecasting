from __future__ import annotations
import logging
from griddemand.features.build import build
from griddemand.models.baseline import seasonal_naive_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    df = build()
    print(f"\nFeature table: {len(df)} rows, {df.shape[1]} columns")
    print(f"Range: {df.ts_utc.min()} -> {df.ts_utc.max()}\n")
    print("Seasonal-naive baselines (test = last 20% of time range):")
    print(seasonal_naive_report(df).to_string(index=False))
    print("\nThese numbers are the bar. Phase 3's model must beat them.")


if __name__ == "__main__":
    main()