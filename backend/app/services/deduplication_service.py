"""
Event Deduplication Service - Semantic Similarity Matching
"""

import logging
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models import AcademicEvent
from app.utils import generate_embedding, calculate_similarity
from app.config import settings

logger = logging.getLogger(__name__)


class DeduplicationService:
    """Service for detecting and handling duplicate academic events"""

    @staticmethod
    def find_duplicate(
        user_id,
        new_event_text: str,
        group_id,
        db: Session,
        threshold: Optional[float] = None
    ) -> Optional[AcademicEvent]:
        """
        Find if a similar event already exists for the user
        Returns the canonical event if duplicate found, None otherwise
        """
        if threshold is None:
            threshold = settings.similarity_threshold

        # Generate embedding for new event
        new_embedding = generate_embedding(new_event_text)
        if not new_embedding:
            logger.warning("Failed to generate embedding for deduplication")
            return None

        # Get recent events for the user (last 30 days)
        from datetime import datetime, timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        recent_events = db.query(AcademicEvent).filter(
            AcademicEvent.user_id == user_id,
            AcademicEvent.created_at >= thirty_days_ago,
            AcademicEvent.is_duplicate == False,  # Only check non-duplicates
        ).all()

        if not recent_events:
            return None

        # Find the most similar event
        best_match = None
        best_similarity = 0.0

        for event in recent_events:
            if not event.embedding:
                continue

            try:
                # Convert embedding string back to list if needed
                event_embedding = event.embedding
                if isinstance(event_embedding, str):
                    import json
                    event_embedding = json.loads(event_embedding)

                similarity = calculate_similarity(new_embedding, event_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = event

            except Exception as e:
                logger.error(f"Error comparing embeddings: {e}")
                continue

        # Return match if similarity exceeds threshold
        if best_similarity >= threshold:
            logger.info(f"Duplicate detected with similarity: {best_similarity}")
            return best_match

        return None

    @staticmethod
    def mark_as_duplicate(
        duplicate_event_id,
        canonical_event_id,
        db: Session
    ) -> bool:
        """Mark an event as a duplicate of another event"""
        try:
            duplicate_event = db.query(AcademicEvent).filter(
                AcademicEvent.id == duplicate_event_id
            ).first()

            if not duplicate_event:
                logger.warning(f"Duplicate event not found: {duplicate_event_id}")
                return False

            duplicate_event.is_duplicate = True
            duplicate_event.canonical_event_id = canonical_event_id

            db.commit()
            logger.info(f"Event {duplicate_event_id} marked as duplicate of {canonical_event_id}")
            return True

        except Exception as e:
            logger.error(f"Error marking event as duplicate: {e}")
            db.rollback()
            return False

    @staticmethod
    def get_canonical_event(event: AcademicEvent, db: Session) -> AcademicEvent:
        """
        Get the canonical (original) event if this is a duplicate
        Returns the canonical event or itself if not a duplicate
        """
        if event.is_duplicate and event.canonical_event_id:
            canonical = db.query(AcademicEvent).filter(
                AcademicEvent.id == event.canonical_event_id
            ).first()

            if canonical:
                return canonical

        return event

    @staticmethod
    def merge_duplicates(
        canonical_event: AcademicEvent,
        duplicates: List[AcademicEvent],
        db: Session
    ) -> int:
        """
        Merge multiple duplicate events into a single canonical event
        Returns the count of merged events
        """
        merged_count = 0

        try:
            for duplicate in duplicates:
                if duplicate.id != canonical_event.id:
                    DeduplicationService.mark_as_duplicate(
                        duplicate.id,
                        canonical_event.id,
                        db
                    )
                    merged_count += 1

            logger.info(f"Merged {merged_count} duplicate events")
            return merged_count

        except Exception as e:
            logger.error(f"Error merging duplicates: {e}")
            db.rollback()
            return 0

    @staticmethod
    def clean_old_duplicates(user_id, db: Session, days: int = 90) -> int:
        """
        Clean up old duplicate event records (older than specified days)
        Returns count of deleted duplicates
        """
        from datetime import datetime, timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        try:
            deleted_count = db.query(AcademicEvent).filter(
                AcademicEvent.user_id == user_id,
                AcademicEvent.is_duplicate == True,
                AcademicEvent.created_at < cutoff_date
            ).delete()

            db.commit()
            logger.info(f"Deleted {deleted_count} old duplicate events")
            return deleted_count

        except Exception as e:
            logger.error(f"Error cleaning old duplicates: {e}")
            db.rollback()
            return 0
