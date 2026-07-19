from __future__ import annotations
import numpy as np
import pandas as pd
from griddemand.features.build import TARGET


def evaluate(y_true: pd.Series, y_pred: pd.Series) -> dict[str, float]:
    mask = y_true.notna() & y_pred.notna()
    y, yhat = y_true[mask], y_pred[mask]
    if len(y) == 0:
        raise ValueError("No overlapping non-NaN values to evaluate")
    return {
        "mae_mw": float(np.mean(np.abs(y - yhat))),
        "mape_pct": float(np.mean(np.abs((y - yhat) / y)) * 100),
        "n": int(len(y)),
    }


def chronological_split(
    df: pd.DataFrame, test_frac: float = 0.2
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.sort_values("ts_utc").reset_index(drop=True)
    cut = int(len(df) * (1 - test_frac))
    return df.iloc[:cut], df.iloc[cut:]


def seasonal_naive_report(df: pd.DataFrame, test_frac: float = 0.2) -> pd.DataFrame:
    _, test = chronological_split(df, test_frac)
    rows = []
    for name, col in [("daily_naive", "lag_48"), ("weekly_naive", "lag_336")]:
        metrics = evaluate(test[TARGET], test[col])
        rows.append({"model": name, **metrics})
    return pd.DataFrame(rows)