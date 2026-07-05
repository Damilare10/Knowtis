"""
Runtime SetFit classifier for WhatsApp academic messages.

The trained model is optional. When it is not installed or not trained yet, the
main classifier falls back to MiniLM anchor similarity and deterministic rules.
"""
import logging
import os
from dataclasses import dataclass
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SetFitPrediction:
    category: str
    confidence: float


class SetFitClassifierService:
    """Lazy-loads a local SetFit model and returns category predictions."""

    _model = None
    _load_failed = False

    @classmethod
    def _get_model(cls):
        if cls._model is not None or cls._load_failed:
            return cls._model

        if not settings.setfit_classifier_enabled:
            cls._load_failed = True
            return None

        model_path = settings.setfit_classifier_path
        if not model_path or not os.path.isdir(model_path):
            cls._load_failed = True
            logger.info("SetFit classifier not found at %s; using fallback classifier", model_path)
            return None

        try:
            from setfit import SetFitModel

            cls._model = SetFitModel.from_pretrained(model_path)
            logger.info("Loaded SetFit classifier from %s", model_path)
            return cls._model
        except Exception as exc:
            cls._load_failed = True
            logger.warning("Failed to load SetFit classifier from %s: %s", model_path, exc)
            return None

    @classmethod
    def classify(cls, text: str) -> Optional[SetFitPrediction]:
        if not text or not text.strip():
            return SetFitPrediction(category="noise", confidence=0.99)

        model = cls._get_model()
        if model is None:
            return None

        try:
            probs = model.predict_proba([text])
            labels = list(getattr(model, "labels", []) or [])
            if probs is not None and labels:
                row = probs[0]
                values = row.tolist() if hasattr(row, "tolist") else list(row)
                best_idx = max(range(len(values)), key=values.__getitem__)
                return SetFitPrediction(
                    category=str(labels[best_idx]),
                    confidence=round(float(values[best_idx]), 4),
                )
        except Exception as exc:
            logger.debug("SetFit probability prediction failed, trying label prediction: %s", exc)

        try:
            predicted = model.predict([text])
            category = predicted[0] if isinstance(predicted, list) else predicted[0].item()
            return SetFitPrediction(category=str(category), confidence=0.70)
        except Exception as exc:
            logger.warning("SetFit classification failed: %s", exc)
            return None
