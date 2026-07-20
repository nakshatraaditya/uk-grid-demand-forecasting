from __future__ import annotations
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path
import mlflow
import pandas as pd
from griddemand import config
from griddemand.models.registry import champion_version, load_champion
from griddemand.models.train import run_training
from griddemand.monitoring.drift import drift_summary, performance_summary, should_retrain

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("monitor")

CURRENT_WINDOW_PERIODS = 7 * 48  
REPORT_DIR = Path("monitoring_reports")


def champion_test_mape() -> float | None:
    try:
        mlflow.set_tracking_uri(config.MLFLOW_TRACKING_URI)
        client = mlflow.MlflowClient()
        version = client.get_model_version_by_alias(config.MODEL_NAME, "champion")
        run = client.get_run(version.run_id)
        return float(run.data.metrics["model_mape_pct"])
    except Exception:
        logger.warning("Could not fetch champion's promoted MAPE", exc_info=True)
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Drift + performance monitoring")
    parser.add_argument("--retrain", action="store_true", help="Retrain if triggered")
    args = parser.parse_args()

    df = pd.read_parquet(config.PROCESSED_DIR / "features.parquet").sort_values("ts_utc")
    if len(df) <= CURRENT_WINDOW_PERIODS * 2:
        raise SystemExit("Not enough data to split reference vs current windows")

    reference, current = df.iloc[:-CURRENT_WINDOW_PERIODS], df.iloc[-CURRENT_WINDOW_PERIODS:]
    logger.info(
        "Reference: %d rows (to %s) | Current: %d rows (from %s)",
        len(reference), reference.ts_utc.max(), len(current), current.ts_utc.min(),
    )

    drift, result = drift_summary(reference, current)
    REPORT_DIR.mkdir(exist_ok=True)
    report_path = REPORT_DIR / f"drift_{datetime.now(timezone.utc):%Y%m%d_%H%M}.html"
    result.save_html(str(report_path))

    model = load_champion()
    perf = performance_summary(model, current, champion_test_mape())

    retrain, reasons = should_retrain(drift, perf)

    print(f"\nDrift: {drift['n_drifted']} drifted features (share {drift['drift_share']:.0%})")
    drifted = [c for c, v in drift["columns"].items() if v["drifted"]]
    if drifted:
        print(f"Drifted columns: {', '.join(drifted)}")
    print(f"Champion v{champion_version()} current MAPE: {perf['current_mape_pct']:.2f}%"
          f" (promoted at {perf['champion_test_mape_pct']:.2f}%)"
          if perf["champion_test_mape_pct"] is not None
          else f"Current MAPE: {perf['current_mape_pct']:.2f}%")
    print(f"Report: {report_path}")

    if not retrain:
        print("\nVerdict: HEALTHY — no retraining needed")
        return

    print("\nVerdict: RETRAIN TRIGGERED")
    for r in reasons:
        print(f"  - {r}")

    if args.retrain:
        print("\nRetraining on full feature table...")
        outcome = run_training(df)
        status = "PROMOTED as new champion" if outcome["promoted"] else "trained but FAILED the gate"
        print(f"New model {status} (MAPE {outcome['model_mape_pct']:.2f}%)")
    else:
        print("(dry run — pass --retrain to act)")


if __name__ == "__main__":
    main()