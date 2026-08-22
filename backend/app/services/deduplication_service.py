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
        threshold: Optional[float] = None,
        event_type: Optional[str] = None,
    ) -> Optional[AcademicEvent]: 
        if threshold is None:
            threshold = max(settings.similarity_threshold, 0.88)

        # Generate embedding for new event
        new_embedding = generate_embedding(new_event_text)
        if not new_embedding:
            logger.warning("Failed to generate embedding for deduplication")
            return None

        # Get recent non-duplicate events for the user (last 30 days)
        from datetime import datetime, timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        query = db.query(AcademicEvent).filter(
            AcademicEvent.user_id == user_id,
            AcademicEvent.created_at >= thirty_days_ago,
            AcademicEvent.is_duplicate == False,
        )
        if event_type:
            query = query.filter(AcademicEvent.event_type == event_type)

        recent_events = query.all()

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
    def reconcile_event(
        user_id,
        event_data: dict,
        group_id,
        db: Session,
    ) -> tuple[Optional[AcademicEvent], str]:
        """
        Reconciles incoming structured event data against existing active events:
        - If action_type == 'UPDATE': finds matching course/title event, updates venue/date/description in place.
        - If action_type == 'CANCEL': marks matching event as cancelled/alert.
        - If duplicate match found: returns (existing_event, 'DUPLICATE').
        - Otherwise: returns (None, 'CREATE') so caller can insert a fresh event.

        Returns: (event_instance_or_none, outcome_status: 'CREATED' | 'UPDATED' | 'CANCELLED' | 'DUPLICATE')
        """
        course_code = event_data.get("course_code")
        action_type = (event_data.get("action_type") or "CREATE").upper()

        from app.services.event_extraction_service import EventExtractionService

        # §3.8: Never mutate on a course-code-less UPDATE/CANCEL — fall through
        # to the duplicate-check / CREATE path instead.
        if action_type in ("UPDATE", "CANCEL") and not course_code:
            action_type = "CREATE"

        from datetime import datetime, timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        query = db.query(AcademicEvent).filter(
            AcademicEvent.user_id == user_id,
            AcademicEvent.created_at >= thirty_days_ago,
            AcademicEvent.is_duplicate == False,
        )
        if course_code:
            query = query.filter(AcademicEvent.course_code == course_code)
        # §3.8: Also match on event_type to avoid cross-type mutations.
        if event_data.get("event_type"):
            query = query.filter(AcademicEvent.event_type == event_data["event_type"])

        matching_events = query.order_by(AcademicEvent.created_at.desc()).all()

        # §3.8: When both incoming and candidates have date_time, prefer the
        # closest match rather than blindly picking the newest row.
        def _pick_target(candidates: list) -> Optional[AcademicEvent]:
            if not candidates:
                return None
            incoming_dt = event_data.get("date_time")
            if incoming_dt and any(c.date_time for c in candidates):
                dated = [c for c in candidates if c.date_time]
                if dated:
                    return min(dated, key=lambda c: abs((c.date_time - incoming_dt).total_seconds()))
            return candidates[0]

        if action_type == "UPDATE" and matching_events:
            target = _pick_target(matching_events)
            if target is None:
                target = matching_events[0]
            ev_desc = event_data.get("description") or ""
            if event_data.get("venue"):
                target.venue = event_data["venue"]
            if event_data.get("date_time"):
                target.date_time = event_data["date_time"]
            if ev_desc and ev_desc not in (target.description or ""):
                target.description = f"{target.description or ''}\nUpdate: {ev_desc}".strip()
            target.updated_at = datetime.utcnow()
            logger.info("Event %s updated via state machine (course=%s)", target.id, course_code)
            return target, "UPDATED"

        if action_type == "CANCEL" and matching_events:
            target = _pick_target(matching_events)
            if target is None:
                target = matching_events[0]
            if not target.title.startswith("[CANCELLED]"):
                target.title = f"[CANCELLED] {target.title}"
            # TODO: [CANCELLED] title prefix is not queryable; step 5 adds a
            # proper `status` column and `superseded_by_id`.
            target.updated_at = datetime.utcnow()
            logger.info("Event %s marked CANCELLED via state machine", target.id)
            return target, "CANCELLED"

        # Check for semantic duplicate — use canonical dedup text (§3.7)
        canonical_text = EventExtractionService.canonical_dedup_text(event_data)
        duplicate = DeduplicationService.find_duplicate(
            user_id=user_id,
            new_event_text=canonical_text,
            group_id=group_id,
            db=db,
            event_type=event_data.get("event_type"),
        )
        if duplicate:
            return duplicate, "DUPLICATE"

        return None, "CREATE"


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
