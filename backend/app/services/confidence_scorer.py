"""
Confidence Scoring Engine for Academic Events
"""
import logging
from typing import Optional, Any, Dict
from sqlalchemy.orm import Session
from app.models import SourceReliability

logger = logging.getLogger(__name__)

class ConfidenceScorer:
    """Computes academic event extraction confidence scores based on multi-factor evidence."""

    @staticmethod
    def calculate_confidence(
        evidence_count: int,
        source_reliability: float,
        entity_clarity: float,
        model_confidence: float = 0.7,
        recency_score: float = 0.7,
        contradiction_penalty: float = 0.0,
    ) -> float:
        """
        Computes a bounded confidence score with capped evidence count.
        """
        if evidence_count <= 0:
            source_count_score = 0.0
        elif evidence_count == 1:
            source_count_score = 0.5
        elif evidence_count == 2:
            source_count_score = 0.8
        else:
            source_count_score = 1.0
        source_reliability = ConfidenceScorer._clamp(source_reliability)
        entity_clarity = ConfidenceScorer._clamp(entity_clarity)
        model_confidence = ConfidenceScorer._clamp(model_confidence)
        recency_score = ConfidenceScorer._clamp(recency_score)
        contradiction_penalty = ConfidenceScorer._clamp(contradiction_penalty)

        confidence = (
            source_count_score * 0.25
            + source_reliability * 0.20
            + entity_clarity * 0.30
            + recency_score * 0.10
            + model_confidence * 0.15
            - contradiction_penalty * 0.30
        )
        return round(ConfidenceScorer._clamp(confidence, 0.1, 0.99), 2)

    @staticmethod
    def evaluate_entity_clarity(course_code: Optional[str], date_time: Optional[Any], venue: Optional[str]) -> float:
        """
        Calculates clarity score [0.0 - 1.0] based on presence of key entities.
        Course Code and Date/Time are high value. Venue is medium value.
        """
        clarity = 0.0
        if course_code:
            clarity += 0.4
        if date_time:
            clarity += 0.4
        if venue:
            clarity += 0.2
        return clarity

    @staticmethod
    def field_confidences(
        course_code: Optional[str],
        date_time: Optional[Any],
        venue: Optional[str],
        classification_confidence: float,
    ) -> Dict[str, float]:
        """Score extracted fields independently so incomplete events can be reviewed safely."""
        base = ConfidenceScorer._clamp(classification_confidence)
        return {
            "course_code": 0.98 if course_code else 0.0,
            "date_time": min(0.90, base + 0.05) if date_time else 0.0,
            "venue": 0.75 if venue else 0.0,
        }

    @staticmethod
    def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
        return min(upper, max(lower, float(value or 0.0)))

    @staticmethod
    def get_source_reliability(sender_jid: Optional[str], db: Session) -> float:
        """Looks up the reliability score for a sender. Defaults to 0.7."""
        if not sender_jid or not db:
            return 0.7

        rel = db.query(SourceReliability).filter(
            SourceReliability.sender_jid == sender_jid
        ).first()

        if rel:
            return rel.reliability_score
        
        # Check if they are a known system contact or rep by naming conventions (heuristic)
        # In a real system, we'd check group participant privileges.
        return 0.7
