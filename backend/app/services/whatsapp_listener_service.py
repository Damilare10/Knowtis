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
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import (
    CoverageState,
    ProcessingStatus,
    RawMessage,
    WhatsAppGroup,
)
from app.services.whatsapp_service import WhatsAppService

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
        Persist a single inbound message idempotently.

        Classification and event extraction have been removed (step 2) — the
        batch writer ``process_message_batch`` is now the only path to
        ``AcademicEvent``.  Messages arrive with ``ai_processed = False`` and
        are picked up on the next 2-minute dispatch cycle.

        Returns True when a new message was stored.
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

        # Single shared hash contract with the prefilter — never reimplement it
        # here, or the two normalisations drift and repeat detection breaks.
        from app.services.prefilter import compute_text_hash

        raw = RawMessage(
            user_id=group.user_id,
            group_id=group_id,
            message_id=message_id,
            sender_jid=msg.get("sender_jid"),
            sender_name=msg.get("sender_name"),
            message_text=text,
            message_type=msg.get("message_type"),
            has_media=bool(msg.get("has_media", False)),
            text_hash=compute_text_hash(text),
            # Ingest only stores the message; process_message_batch is what
            # processes it. Claiming PROCESSED here would make the field
            # meaningless and contradict the SKIPPED_*/QUARANTINED members.
            processing_status=ProcessingStatus.PENDING if text else ProcessingStatus.SKIPPED_EMPTY,
        )
        db.add(raw)
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
            group.coverage_state = CoverageState.ACTIVE
            group.last_coverage_update = datetime.utcnow()
            if group.outage_start:
                group.outage_end = datetime.utcnow()
            db.commit()

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
                    # and stuck RECOVERING groups that couldn't self-heal.
                    prev_state = group.coverage_state
                    if group.coverage_state in (CoverageState.DEGRADED, CoverageState.RECOVERING):
                        group.coverage_state = CoverageState.ACTIVE
                        group.last_coverage_update = datetime.utcnow()
                        if group.outage_start:
                            group.outage_end = datetime.utcnow()
                        summary["recovered"] += 1
                        logger.info("Coverage for %s recovered to ACTIVE from %s", group.group_jid, prev_state)

            db.commit()
            return summary
        except Exception as exc:
            logger.error("Bot removal detection failed: %s", exc)
            db.rollback()
            return summary
        finally:
            if owns_session and db is not None:
                db.close()
