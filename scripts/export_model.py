from __future__ import annotations
import shutil
from pathlib import Path
import mlflow
from griddemand.models.registry import champion_version, load_champion

EXPORT_DIR = Path("model_export")


def main() -> None:
    model = load_champion()
    version = champion_version()

    if EXPORT_DIR.exists():
        shutil.rmtree(EXPORT_DIR)
    mlflow.lightgbm.save_model(model, path=str(EXPORT_DIR))
    (EXPORT_DIR / "champion_version.txt").write_text(str(version))

    print(f"Exported champion v{version} -> {EXPORT_DIR.resolve()}")


if __name__ == "__main__":
    main()