"""
WhatsApp Headless Listener Service

Implements the WhatsApp connector abstraction layer described in PRD section
6.10 (Connector Abstraction Layer). The core application talks to an abstract
:class:`WhatsAppConnectorInterface`; the default adapter
(:class:`LocalHttpPollingAdapter`) polls the external WhatsApp connector over
HTTP with exponential backoff and graceful fallback when it is unreachable.

Responsibilities:
    * Poll each ACTIVE group for new messages and ingest them (idempotent via
      ``RawMessage.message_id`` deduplication + semantic dedup).
    * Apply exponential backoff per group when the connector is unreachable and
      transition connectivity-degraded groups to ``DEGRADED``.
    * Self-initiated bot-removal detection (``detect_bot_removal``) that checks
      group membership and transitions removed bots to ``PAUSED``.

The listener is driven by a Celery beat task defined in ``app.tasks``.
"""
import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import (
    AcademicEvent,
    CoverageState,
    EventType,
    ProcessingStatus,
    RawMessage,
    ReminderState,
    WhatsAppGroup,
)
from app.services.classifier_service import Classification, MessageClassifier
from app.services.deduplication_service import DeduplicationService
from app.services.notification_service import NotificationService
from app.services.training_feedback_service import TrainingFeedbackService
from app.services.whatsapp_service import WhatsAppService
from app.utils import generate_embedding

logger = logging.getLogger(__name__)


class WhatsAppConnectorInterface(ABC):
    """Abstract connector interface isolating WhatsApp protocol details."""

    @abstractmethod
    async def fetch_new_messages(
        self, group_jid: str, since: Optional[str] = None, limit: Optional[int] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """Return new messages, or None when the connector is unreachable."""

    @abstractmethod
    async def check_membership(self, group_jid: str) -> Optional[bool]:
        """Return True/False for bot membership, or None when unreachable."""

    @abstractmethod
    async def health(self) -> Optional[Dict[str, Any]]:
        """Return connector health info, or None when unreachable."""


class LocalHttpPollingAdapter(WhatsAppConnectorInterface):
    """Default adapter that polls the external HTTP WhatsApp connector."""

    def __init__(self, service: Optional[WhatsAppService] = None) -> None:
        self.service = service or WhatsAppService()

    async def fetch_new_messages(
        self, group_jid: str, since: Optional[str] = None, limit: Optional[int] = None
    ) -> Optional[List[Dict[str, Any]]]:
        return await self.service.fetch_messages(group_jid, since=since, limit=limit)

    async def check_membership(self, group_jid: str) -> Optional[bool]:
        return await self.service.is_bot_member(group_jid)

    async def health(self) -> Optional[Dict[str, Any]]:
        return await self.service.health()


class WhatsAppListenerService:
    """Headless listener driving message ingestion and coverage tracking."""

    def __init__(self, adapter: Optional[WhatsAppConnectorInterface] = None) -> None:
        self.adapter = adapter or LocalHttpPollingAdapter()
        # consecutive connector failures per group_jid (for exponential backoff)
        self._failures: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Backoff helpers
    # ------------------------------------------------------------------
    def _backoff_seconds(self, failures: int) -> float:
        base = settings.whatsapp_listener_poll_interval
        if failures <= 0:
            return float(base)
        delay = base * (2 ** (failures - 1))
        return float(min(delay, settings.whatsapp_listener_max_backoff))

    def _should_skip_for_backoff(self, group_jid: str) -> bool:
        """True when a group is still in its backoff window."""
        failures = self._failures.get(group_jid, 0)
        return failures > 0 and failures < 3  # only short-circuit transient blips

    # ------------------------------------------------------------------
    # Checkpointing
    # ------------------------------------------------------------------
    @staticmethod
    def _latest_message_marker(group_id, db: Session) -> Optional[str]:
        """Return the most recent stored message_id for a group (idempotent resume)."""
        latest = (
            db.query(RawMessage.message_id)
            .filter(RawMessage.group_id == group_id)
            .order_by(RawMessage.created_at.desc())
            .first()
        )
        return latest[0] if latest else None

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------
    def ingest_message(self, group: WhatsAppGroup, msg: Dict[str, Any], db: Session) -> bool:
        """
        Persist a single inbound message idempotently and run classification +
        semantic dedup. Returns True when a new message was stored.
        """
        message_id = msg.get("message_id") or self._synthesize_id(msg)
        group_id = group.id

        existing = (
            db.query(RawMessage.id)
            .filter(RawMessage.group_id == group_id, RawMessage.message_id == message_id)
            .first()
        )
        if existing:
            return False  # already ingested -> idempotent no-op

        text = msg.get("message_text") or ""
        classification: Optional[str] = None
        confidence: Optional[float] = None

        if text:
            label, conf = MessageClassifier.classify_message(text)
            classification = label.value
            confidence = conf

        raw = RawMessage(
            user_id=group.user_id,
            group_id=group_id,
            message_id=message_id,
            sender_jid=msg.get("sender_jid"),
            sender_name=msg.get("sender_name"),
            message_text=text,
            message_type=msg.get("message_type"),
            has_media=bool(msg.get("has_media", False)),
            classification=classification,
            confidence_score=confidence,
            processing_status=ProcessingStatus.PROCESSED if text else ProcessingStatus.PENDING,
        )
        db.add(raw)

        if text and classification == Classification.SIGNAL.value:
            try:
                self._extract_event(group, raw, text, db)
            except Exception as exc:
                logger.error(
                    "Event extraction/deduplication failed for raw message %s: %s",
                    message_id,
                    exc,
                    exc_info=True,
                )
                raw.processing_status = ProcessingStatus.FAILED

        db.commit()
        return True

    @staticmethod
    def _synthesize_id(msg: Dict[str, Any]) -> str:
        import hashlib

        seed = "|".join(
            str(msg.get(k, ""))
            for k in ("sender_jid", "message_text", "timestamp")
        )
        return hashlib.sha1(seed.encode("utf-8")).hexdigest()

    @staticmethod
    def _extract_event(
        group: WhatsAppGroup, raw: RawMessage, text: str, db: Session
    ) -> None:
        """Classify a signal message into a structured academic event with dedup."""
        from app.services.event_extraction_service import EventExtractionService

        event_data = EventExtractionService.extract_event(text, db=db, msg_created_at=raw.created_at)
        if not event_data:
            return

        embedding = generate_embedding(text)
        event = AcademicEvent(
            user_id=group.user_id,
            group_id=group.id,
            event_type=EventType(event_data["event_type"]),
            course_code=event_data.get("course_code"),
            title=event_data["title"][:500],
            description=event_data.get("description"),
            venue=event_data.get("venue"),
            date_time=event_data.get("date_time"),
            reminder_state=ReminderState.PENDING,
            urgency_score=event_data["urgency_score"],
            confidence_score=event_data["confidence_score"],
            relevance_score=event_data["relevance_score"],
            actionability_score=event_data["actionability_score"],
            embedding=json.dumps(embedding) if embedding else None,
            source_message_id=raw.message_id,
            source_group_jid=group.group_jid,
        )
        db.add(event)
        db.flush()

        TrainingFeedbackService.record_prediction(
            db=db,
            user_id=group.user_id,
            message_text=text,
            event_data=event_data,
            raw_message_id=raw.id,
            academic_event_id=event.id,
        )

        duplicate = DeduplicationService.find_duplicate(
            user_id=group.user_id,
            new_event_text=text,
            group_id=group.id,
            db=db,
        )
        if duplicate and duplicate.id != event.id:
            DeduplicationService.mark_as_duplicate(event.id, duplicate.id, db)

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------
    async def poll_group(self, group: WhatsAppGroup, db: Session) -> int:
        """
        Poll a single group for new messages and ingest them.
        Returns the number of newly ingested messages.
        """
        group_jid = group.group_jid

        if self._should_skip_for_backoff(group_jid):
            logger.debug("Skipping %s while in backoff", group_jid)
            return 0

        since = self._latest_message_marker(group.id, db)
        limit = settings.recovery_backfill_limit
        messages = await self.adapter.fetch_new_messages(group_jid, since=since, limit=limit)

        if messages is None:
            self._handle_connector_failure(group, db)
            return 0

        # Connector reachable -> reset backoff and recover connectivity-based degradation
        self._failures[group_jid] = 0
        if group.coverage_state == CoverageState.DEGRADED:
            logger.info("Connector recovered for %s; connectivity restored", group_jid)

        ingested = 0
        for msg in messages:
            try:
                if self.ingest_message(group, msg, db):
                    ingested += 1
            except Exception as exc:
                logger.error("Failed to ingest message for %s: %s", group_jid, exc)
                db.rollback()
        if ingested:
            logger.info("Ingested %d new message(s) for %s", ingested, group_jid)
        return ingested

    def _handle_connector_failure(self, group: WhatsAppGroup, db: Session) -> None:
        group_jid = group.group_jid
        failures = self._failures.get(group_jid, 0) + 1
        self._failures[group_jid] = failures
        delay = self._backoff_seconds(failures)
        logger.warning(
            "WhatsApp connector unreachable for %s (attempt %d); backing off %.1fs",
            group_jid, failures, delay,
        )
        # Transition to DEGRADED after repeated transient failures
        if failures >= 2 and group.coverage_state == CoverageState.ACTIVE:
            group.coverage_state = CoverageState.DEGRADED
            group.last_coverage_update = datetime.utcnow()
            if not group.outage_start:
                group.outage_start = datetime.utcnow()
            db.commit()
            logger.warning("Group %s transitioned to DEGRADED (connector unreachable)", group_jid)

    async def run_listener_cycle(self, db: Optional[Session] = None) -> int:
        """
        Drive one polling cycle across all ACTIVE/DEGRADED groups.
        Returns the total number of newly ingested messages.
        """
        if not settings.whatsapp_listener_enabled:
            logger.debug("WhatsApp listener disabled; skipping cycle")
            return 0

        owns_session = db is None
        if owns_session:
            db = SessionLocal()
        try:
            groups = (
                db.query(WhatsAppGroup)
                .filter(
                    WhatsAppGroup.is_active == True,  # noqa: E712
                    WhatsAppGroup.coverage_state.in_(
                        [CoverageState.ACTIVE, CoverageState.DEGRADED]
                    ),
                )
                .all()
            )
            total = 0
            for group in groups:
                total += await self.poll_group(group, db)
            return total
        finally:
            if owns_session and db is not None:
                db.close()

    # ------------------------------------------------------------------
    # Bot removal detection
    # ------------------------------------------------------------------
    async def detect_bot_removal(self, db: Optional[Session] = None) -> Dict[str, int]:
        """
        Self-initiated coverage check: verifies bot membership for each monitored
        group and transitions coverage state accordingly.

        - bot removed / False -> PAUSED (outage tracked, users notified)
        - connector unreachable / None -> DEGRADED (do not assume removal)
        - bot present / True -> ACTIVE (recover from DEGRADED)

        Returns a summary dict of state transitions performed.
        """
        owns_session = db is None
        if owns_session:
            db = SessionLocal()
        summary = {"paused": 0, "degraded": 0, "recovered": 0, "checked": 0}
        try:
            groups = (
                db.query(WhatsAppGroup)
                .filter(
                    WhatsAppGroup.is_active == True,  # noqa: E712
                    WhatsAppGroup.coverage_state.in_(
                        [CoverageState.ACTIVE, CoverageState.DEGRADED, CoverageState.RECOVERING]
                    ),
                )
                .all()
            )

            for group in groups:
                summary["checked"] += 1
                membership = await self.adapter.check_membership(group.group_jid)

                if membership is None:
                    # Cannot determine membership -> mark DEGRADED, never PAUSED
                    if group.coverage_state == CoverageState.ACTIVE:
                        group.coverage_state = CoverageState.DEGRADED
                        group.last_coverage_update = datetime.utcnow()
                        if not group.outage_start:
                            group.outage_start = datetime.utcnow()
                        summary["degraded"] += 1
                        logger.warning(
                            "Coverage for %s degraded (connector unreachable)",
                            group.group_jid,
                        )
                elif membership is False:
                    # Bot definitively removed -> PAUSED
                    if group.coverage_state != CoverageState.PAUSED:
                        group.coverage_state = CoverageState.PAUSED
                        group.last_coverage_update = datetime.utcnow()
                        if not group.outage_start:
                            group.outage_start = datetime.utcnow()
                        summary["paused"] += 1
                        logger.warning(
                            "Bot removed from %s; coverage PAUSED", group.group_jid
                        )
                        NotificationService.send_system_message(
                            user_id=group.user_id,
                            title="WhatsApp coverage paused",
                            description=(
                                f"Monitoring for '{group.group_name}' was paused because "
                                "the listener was removed or disconnected. "
                                "Some academic updates may be missed until recovery."
                            ),
                            db=db,
                        )
                else:
                    # Bot present -> recover connectivity-based degradation
                    if group.coverage_state == CoverageState.DEGRADED:
                        group.coverage_state = CoverageState.ACTIVE
                        group.last_coverage_update = datetime.utcnow()
                        summary["recovered"] += 1
                        logger.info("Coverage for %s recovered to ACTIVE", group.group_jid)

            db.commit()
            return summary
        except Exception as exc:
            logger.error("Bot removal detection failed: %s", exc)
            db.rollback()
            return summary
        finally:
            if owns_session and db is not None:
                db.close()
