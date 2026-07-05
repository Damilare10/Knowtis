"""
Helpers for collecting production predictions and exporting safe training data.
"""
import re
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models import PredictionRecord


class TrainingFeedbackService:
    """Persistence and sanitization helpers for the offline learning loop."""

    MODEL_VERSION = "fallback-v1"

    @staticmethod
    def record_prediction(
        db: Session,
        user_id,
        message_text: str,
        event_data: Dict[str, Any],
        raw_message_id=None,
        academic_event_id=None,
    ) -> PredictionRecord:
        prediction = PredictionRecord(
            user_id=user_id,
            raw_message_id=raw_message_id,
            academic_event_id=academic_event_id,
            message_text=message_text,
            predicted_category=event_data.get("academic_category"),
            predicted_confidence=event_data.get("confidence_score"),
            event_type=event_data.get("event_type"),
            event_completeness=event_data.get("event_completeness"),
            actionability=event_data.get("actionability"),
            needs_review=bool(event_data.get("needs_review")),
            field_confidence=event_data.get("field_confidence"),
            model_version=TrainingFeedbackService.MODEL_VERSION,
        )
        db.add(prediction)
        return prediction

    @staticmethod
    def sanitize_message(text: str) -> str:
        """Remove common personal identifiers before using feedback for training."""
        if not text:
            return ""

        sanitized = text
        sanitized = re.sub(r"\b(?:\+?234|0)\d{10}\b", "[PHONE]", sanitized)
        sanitized = re.sub(r"\b\d{2}/\d{3,6}\b", "[MATRIC]", sanitized)
        sanitized = re.sub(r"\b\d{6,12}\b", "[NUMBER]", sanitized)
        sanitized = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[EMAIL]", sanitized, flags=re.IGNORECASE)
        return sanitized.strip()

    @staticmethod
    def category_for_feedback(prediction: PredictionRecord, corrected_category: Optional[str]) -> str:
        if corrected_category:
            return corrected_category
        return prediction.predicted_category or "noise"
