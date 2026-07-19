from __future__ import annotations
import logging
import lightgbm as lgb
import mlflow
import pandas as pd
from griddemand import config
from griddemand.features.build import FEATURE_COLS, TARGET
from griddemand.models.baseline import chronological_split, evaluate

logger = logging.getLogger(__name__)

DEFAULT_PARAMS = {
    "objective": "regression_l1",  
    "num_leaves": 63,
    "min_data_in_leaf": 20,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.9,
    "bagging_freq": 1,
    "verbosity": -1,
    "seed": 42,
}


def three_way_split(
    df: pd.DataFrame, test_frac: float = 0.2, valid_frac: float = 0.2
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_valid, test = chronological_split(df, test_frac)
    train, valid = chronological_split(train_valid, valid_frac)
    return train, valid, test


def train_and_evaluate(
    df: pd.DataFrame,
    params: dict | None = None,
    num_boost_round: int = 2000,
    early_stopping_rounds: int = 100,
) -> tuple[lgb.Booster, dict, pd.DataFrame]:
    params = {**DEFAULT_PARAMS, **(params or {})}
    train, valid, test = three_way_split(df)

    dtrain = lgb.Dataset(train[FEATURE_COLS], label=train[TARGET])
    dvalid = lgb.Dataset(valid[FEATURE_COLS], label=valid[TARGET], reference=dtrain)

    model = lgb.train(
        params,
        dtrain,
        num_boost_round=num_boost_round,
        valid_sets=[dvalid],
        callbacks=[lgb.early_stopping(early_stopping_rounds, verbose=False)],
    )

    test = test.copy()
    test["pred"] = model.predict(test[FEATURE_COLS], num_iteration=model.best_iteration)

    metrics = {
        "model_" + k: v for k, v in evaluate(test[TARGET], test["pred"]).items()
    }
    metrics |= {
        "daily_naive_" + k: v for k, v in evaluate(test[TARGET], test["lag_48"]).items()
    }
    metrics["best_iteration"] = model.best_iteration
    return model, metrics, test


def run_training(df: pd.DataFrame, params: dict | None = None) -> dict:
    mlflow.set_tracking_uri(config.MLFLOW_TRACKING_URI)
    mlflow.set_experiment(config.MLFLOW_EXPERIMENT)

    with mlflow.start_run() as run:
        model, metrics, test = train_and_evaluate(df, params)

        mlflow.log_params({**DEFAULT_PARAMS, **(params or {})})
        mlflow.log_param("n_rows", len(df))
        mlflow.log_param("data_start", str(df.ts_utc.min()))
        mlflow.log_param("data_end", str(df.ts_utc.max()))
        mlflow.log_metrics({k: v for k, v in metrics.items() if isinstance(v, (int, float))})

        # Feature importance: log as an artifact for later inspection.
        imp = pd.DataFrame(
            {"feature": FEATURE_COLS, "gain": model.feature_importance("gain")}
        ).sort_values("gain", ascending=False)
        mlflow.log_table(imp, "feature_importance.json")

        beats_baseline = metrics["model_mape_pct"] < metrics["daily_naive_mape_pct"]
        mlflow.set_tag("beats_baseline", str(beats_baseline))

        promoted = False
        if beats_baseline:
            logged = mlflow.lightgbm.log_model(
                model, name="model", registered_model_name=config.MODEL_NAME
            )
            version = logged.registered_model_version
            client = mlflow.MlflowClient()
            client.set_registered_model_alias(config.MODEL_NAME, "champion", version)
            promoted = True
            logger.info(
                "PROMOTED: version %s is the new champion (%.2f%% < %.2f%% baseline)",
                version, metrics["model_mape_pct"], metrics["daily_naive_mape_pct"],
            )
        else:
            mlflow.lightgbm.log_model(model, name="model")
            logger.warning(
                "GATE FAILED: model %.2f%% did not beat baseline %.2f%% — not promoted",
                metrics["model_mape_pct"], metrics["daily_naive_mape_pct"],
            )

        return {"run_id": run.info.run_id, "promoted": promoted, **metrics}