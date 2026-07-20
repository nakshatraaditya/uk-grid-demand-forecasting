from __future__ import annotations
import json
import logging
import pandas as pd
from evidently import Report
from evidently.presets import DataDriftPreset
from griddemand.features.build import FEATURE_COLS, TARGET
from griddemand.models.baseline import evaluate

logger = logging.getLogger(__name__)

DRIFT_SHARE_THRESHOLD = 0.30
DEGRADATION_FACTOR = 1.25


def drift_summary(reference: pd.DataFrame, current: pd.DataFrame):
    cols = FEATURE_COLS + [TARGET]
    result = Report([DataDriftPreset()]).run(
        reference_data=reference[cols], current_data=current[cols]
    )
    payload = json.loads(result.json())

    summary: dict = {"columns": {}}
    for metric in payload["metrics"]:
        name = metric["metric_name"]
        if name.startswith("DriftedColumnsCount"):
            summary["n_drifted"] = int(metric["value"]["count"])
            summary["drift_share"] = float(metric["value"]["share"])
        elif name.startswith("ValueDrift"):
            col = metric["config"]["column"]
            method = metric["config"]["method"]
            threshold = float(metric["config"]["threshold"])
            value = float(metric["value"])
            drifted = value < threshold if "p_value" in method else value > threshold
            summary["columns"][col] = {
                "value": value, "method": method, "drifted": drifted,
            }
    return summary, result


def performance_summary(
    model, current: pd.DataFrame, champion_test_mape: float | None
) -> dict:
    preds = pd.Series(model.predict(current[FEATURE_COLS]), index=current.index)
    metrics = evaluate(current[TARGET], preds)
    out = {
        "current_mape_pct": metrics["mape_pct"],
        "current_mae_mw": metrics["mae_mw"],
        "champion_test_mape_pct": champion_test_mape,
        "degraded": False,
    }
    if champion_test_mape is not None:
        out["degraded"] = metrics["mape_pct"] > champion_test_mape * DEGRADATION_FACTOR
    return out


def should_retrain(drift: dict, performance: dict) -> tuple[bool, list[str]]:
    reasons = []
    if drift.get("drift_share", 0) > DRIFT_SHARE_THRESHOLD:
        reasons.append(
            f"data drift: {drift['n_drifted']} features drifted "
            f"(share {drift['drift_share']:.0%} > {DRIFT_SHARE_THRESHOLD:.0%})"
        )
    if performance.get("degraded"):
        reasons.append(
            f"performance: current MAPE {performance['current_mape_pct']:.2f}% > "
            f"{DEGRADATION_FACTOR}x promoted MAPE "
            f"({performance['champion_test_mape_pct']:.2f}%)"
        )
    return bool(reasons), reasons