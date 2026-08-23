"""
Event Deduplication Service - Semantic Similarity Matching & Business Key Matching
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from app.models import AcademicEvent, EventStatus, Reminder, ReminderState
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
        course_code: Optional[str] = None,
        date_time: Optional[datetime] = None,
    ) -> Optional[AcademicEvent]:
        """
        Find duplicate academic event:
        1. Exact business key lookup: (user_id, course_code, event_type, date(date_time))
        2. Vector similarity fallback: threshold >= 0.92 when business key is incomplete.
        """
        if threshold is None:
            threshold = max(settings.similarity_threshold, 0.92)

        # 1. Exact business key check — indexed, fast, catches exact duplicates
        if course_code and event_type and date_time:
            target_date = date_time.date() if isinstance(date_time, datetime) else None
            if target_date:
                hit = db.query(AcademicEvent).filter(
                    AcademicEvent.user_id == user_id,
                    AcademicEvent.course_code == course_code,
                    AcademicEvent.event_type == event_type,
                    AcademicEvent.is_duplicate == False,
                    AcademicEvent.is_archived == False,
                    func.date(AcademicEvent.date_time) == target_date,
                ).first()
                if hit:
                    logger.info("Business key duplicate hit: %s for course %s on %s", hit.id, course_code, target_date)
                    return hit

        # 2. Vector similarity fallback only when business key is incomplete or misses
        new_embedding = generate_embedding(new_event_text)
        if not new_embedding:
            logger.warning("Failed to generate embedding for deduplication")
            return None

        # Check database dialect for pgvector execution vs SQLite fallback
        is_postgres = False
        if db.bind:
            is_postgres = "postgresql" in str(db.bind.url)

        if is_postgres:
            try:
                vector_str = f"[{','.join(map(str, new_embedding))}]"
                sql = text("""
                    SELECT id, similarity
                    FROM (
                        SELECT id,
                               (1.0 - (COALESCE(embedding_vec, CAST(embedding AS vector)) <=> CAST(:query_vector AS vector))) AS similarity
                        FROM academic_events
                        WHERE user_id = :user_id
                          AND is_duplicate = False
                          AND is_archived = False
                    ) AS scored
                    WHERE similarity >= :threshold
                    ORDER BY similarity DESC
                    LIMIT 1
                """)
                row = db.execute(sql, {
                    "user_id": user_id,
                    "query_vector": vector_str,
                    "threshold": threshold,
                }).first()
                if row:
                    logger.info("pgvector duplicate detected with similarity: %s", row.similarity)
                    return db.query(AcademicEvent).filter(AcademicEvent.id == row.id).first()
                return None
            except Exception as e:
                logger.error(f"Postgres pgvector deduplication search failed: {e}. Falling back to Python cosine comparison.")

        # Local SQLite / Python fallback
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        query = db.query(AcademicEvent).filter(
            AcademicEvent.user_id == user_id,
            AcademicEvent.created_at >= thirty_days_ago,
            AcademicEvent.is_duplicate == False,
            AcademicEvent.is_archived == False,
        )
        if event_type:
            query = query.filter(AcademicEvent.event_type == event_type)

        recent_events = query.all()
        if not recent_events:
            return None

        best_match = None
        best_similarity = 0.0

        for event in recent_events:
            if not event.embedding:
                continue

            try:
                event_embedding = event.embedding
                if isinstance(event_embedding, str):
                    event_embedding = json.loads(event_embedding)

                similarity = calculate_similarity(new_embedding, event_embedding)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = event
            except Exception as e:
                logger.error(f"Error comparing embeddings: {e}")
                continue

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
        - If action_type == 'UPDATE': finds matching event by (course_code, event_type, nearest date_time ±7d),
          updates venue/date/description in place, and records revision.
        - If action_type == 'CANCEL': marks matching event status = CANCELLED, dismisses pending reminders,
          records revision, and leaves title clean.
        - If duplicate match found: returns (existing_event, 'DUPLICATE').
        - Otherwise: returns (None, 'CREATE') so caller can insert a fresh event.

        Returns: (event_instance_or_none, outcome_status: 'CREATED' | 'UPDATED' | 'CANCELLED' | 'DUPLICATE')
        """
        course_code = event_data.get("course_code")
        action_type = (event_data.get("action_type") or "CREATE").upper()

        from app.services.event_extraction_service import EventExtractionService

        # Never mutate on a course-code-less UPDATE/CANCEL — fall through to duplicate-check / CREATE
        if action_type in ("UPDATE", "CANCEL") and not course_code:
            action_type = "CREATE"

        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        query = db.query(AcademicEvent).filter(
            AcademicEvent.user_id == user_id,
            AcademicEvent.created_at >= thirty_days_ago,
            AcademicEvent.is_duplicate == False,
            AcademicEvent.is_archived == False,
        )
        if course_code:
            query = query.filter(AcademicEvent.course_code == course_code)
        if event_data.get("event_type"):
            query = query.filter(AcademicEvent.event_type == event_data["event_type"])

        matching_events = query.order_by(AcademicEvent.created_at.desc()).all()

        def _pick_target(candidates: list) -> Optional[AcademicEvent]:
            if not candidates:
                return None
            incoming_dt = event_data.get("date_time")
            if incoming_dt and any(c.date_time for c in candidates):
                dated = [c for c in candidates if c.date_time]
                within_7_days = [c for c in dated if abs((c.date_time - incoming_dt).total_seconds()) <= 7 * 86400]
                if within_7_days:
                    return min(within_7_days, key=lambda c: abs((c.date_time - incoming_dt).total_seconds()))
                return min(dated, key=lambda c: abs((c.date_time - incoming_dt).total_seconds()))
            return candidates[0]

        if action_type == "UPDATE" and matching_events:
            target = _pick_target(matching_events)
            if target is None:
                target = matching_events[0]

            changes = {}
            if event_data.get("venue") and target.venue != event_data["venue"]:
                changes["venue"] = {"old": target.venue, "new": event_data["venue"]}
                target.venue = event_data["venue"]
            if event_data.get("date_time") and target.date_time != event_data["date_time"]:
                changes["date_time"] = {"old": str(target.date_time), "new": str(event_data["date_time"])}
                target.date_time = event_data["date_time"]
            if event_data.get("title") and target.title != event_data["title"]:
                changes["title"] = {"old": target.title, "new": event_data["title"]}
                target.title = event_data["title"]
            if event_data.get("description"):
                changes["description"] = event_data["description"]
                if not target.description:
                    target.description = event_data["description"]

            rev = list(target.revisions or [])
            rev.append({
                "action": "UPDATE",
                "timestamp": datetime.utcnow().isoformat(),
                "source_message_id": event_data.get("source_message_id"),
                "changes": changes,
            })
            target.revisions = rev
            target.updated_at = datetime.utcnow()
            logger.info("Event %s updated via state machine (course=%s)", target.id, course_code)
            return target, "UPDATED"

        if action_type == "CANCEL" and matching_events:
            target = _pick_target(matching_events)
            if target is None:
                target = matching_events[0]

            target.status = EventStatus.CANCELLED
            target.reminder_state = ReminderState.DISMISSED

            # Deactivate pending reminders for this event
            db.query(Reminder).filter(
                Reminder.event_id == target.id,
                Reminder.is_active == True,
            ).update({"is_active": False}, synchronize_session=False)

            rev = list(target.revisions or [])
            rev.append({
                "action": "CANCEL",
                "timestamp": datetime.utcnow().isoformat(),
                "source_message_id": event_data.get("source_message_id"),
                "reason": event_data.get("description") or "Cancelled via message",
            })
            target.revisions = rev
            target.updated_at = datetime.utcnow()
            logger.info("Event %s marked CANCELLED (status=CANCELLED)", target.id)
            return target, "CANCELLED"

        # Check for semantic duplicate using business key first and canonical dedup text
        canonical_text = EventExtractionService.canonical_dedup_text(event_data)
        duplicate = DeduplicationService.find_duplicate(
            user_id=user_id,
            new_event_text=canonical_text,
            group_id=group_id,
            db=db,
            threshold=0.92,
            event_type=event_data.get("event_type"),
            course_code=course_code,
            date_time=event_data.get("date_time"),
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
