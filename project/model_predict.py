from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
from sklearn.pipeline import Pipeline

from .feature_extraction import FeatureVector


@dataclass(frozen=True)
class Prediction:
    label: str
    confidence: float
    probabilities: dict[str, float]


class EmgClassifier:
    def __init__(self, model: Pipeline):
        self._model = model

    @staticmethod
    def load(model_path: Path) -> "EmgClassifier":
        model = joblib.load(model_path)
        if not isinstance(model, Pipeline):
            raise ValueError("invalid_model_type")
        return EmgClassifier(model)

    def predict(self, fv: FeatureVector) -> Optional[Prediction]:
        x = fv.to_array().reshape(1, -1)
        try:
            proba = self._model.predict_proba(x)[0]
            classes = list(self._model.named_steps["clf"].classes_)
            probs = {str(c): float(p) for c, p in zip(classes, proba)}
            label = str(classes[int(np.argmax(proba))])
            conf = float(np.max(proba))
            return Prediction(label=label, confidence=conf, probabilities=probs)
        except Exception:
            try:
                label = str(self._model.predict(x)[0])
                return Prediction(label=label, confidence=1.0, probabilities={label: 1.0})
            except Exception:
                return None

