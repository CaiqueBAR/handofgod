from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

try:
    from .feature_extraction import FeatureVector
except ImportError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from project.feature_extraction import FeatureVector


@dataclass(frozen=True)
class TrainingResult:
    model_path: Path
    report: str


def load_feature_dataset(csv_path: Path) -> tuple[np.ndarray, np.ndarray]:
    feature_names = FeatureVector.feature_names()
    x_rows: list[list[float]] = []
    y_rows: list[str] = []

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("csv_missing_header")
        for row in reader:
            label = (row.get("label") or "").strip()
            if not label:
                continue
            try:
                feats = [float(row[name]) for name in feature_names]
            except Exception:
                continue
            x_rows.append(feats)
            y_rows.append(label)

    if not x_rows:
        raise ValueError("dataset_empty_or_invalid")

    return np.asarray(x_rows, dtype=np.float64), np.asarray(y_rows, dtype=object)


def train_model(x: np.ndarray, y: np.ndarray, seed: int = 42) -> tuple[Pipeline, str]:
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, random_state=seed, stratify=y if len(set(y)) > 1 else None
    )

    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=300,
                    random_state=seed,
                    class_weight="balanced_subsample",
                    n_jobs=-1,
                ),
            ),
        ]
    )

    model.fit(x_train, y_train)
    y_pred = model.predict(x_test)
    report = classification_report(y_test, y_pred, zero_division=0)
    return model, report


def save_model(model: Pipeline, model_path: Path) -> None:
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, help="CSV de features (gerado pelo emg_interface)")
    parser.add_argument("--out", default=str(Path("project") / "models" / "emg_model.joblib"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    model_path = Path(args.out)

    x, y = load_feature_dataset(dataset_path)
    model, report = train_model(x, y, seed=args.seed)
    save_model(model, model_path)
    print(report)
    print(f"MODEL_SAVED={model_path}")


if __name__ == "__main__":
    main()
