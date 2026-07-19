from __future__ import annotations
import logging
import pandas as pd
from griddemand import config
from griddemand.models.train import run_training

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    df = pd.read_parquet(config.PROCESSED_DIR / "features.parquet")
    result = run_training(df)

    print(f"\nRun: {result['run_id']}")
    print(f"Model      : MAPE {result['model_mape_pct']:.2f}%  MAE {result['model_mae_mw']:.0f} MW")
    print(f"Daily naive: MAPE {result['daily_naive_mape_pct']:.2f}%  MAE {result['daily_naive_mae_mw']:.0f} MW")
    print(f"Best iteration: {result['best_iteration']}")
    print(f"Promoted to champion: {result['promoted']}")


if __name__ == "__main__":
    main()