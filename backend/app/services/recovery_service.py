"""
WhatsApp Recovery & Reconciliation Service

Implements PRD section 6.10 (Recovery & Rejoin Logic). Periodically scans groups
in ``DEGRADED``/``PAUSED``/``RECOVERING`` coverage states, attempts re-join via
the WhatsApp connector, re-ingests missed messages (idempotent via message-id
deduplication), and transitions coverage state to ``ACTIVE``/``RECOVERING`` as
appropriate.

Scheduled via Celery beat in ``app.tasks``.
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import CoverageState, WhatsAppGroup
from app.services.whatsapp_listener_service import WhatsAppListenerService
from app.services.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)


class RecoveryService:
    """Reconciles degraded/paused WhatsApp groups back to ACTIVE coverage."""

    def __init__(
        self,
        service: Optional[WhatsAppService] = None,
        listener: Optional[WhatsAppListenerService] = None,
    ) -> None:
        self.service = service or WhatsAppService()
        self.listener = listener or WhatsAppListenerService()

    async def reconcile_groups(self, db: Optional[Session] = None) -> Dict[str, int]:
        """
        Scan groups needing recovery and attempt re-join + backfill.

        Returns a summary: {scanned, rejoined, backfilled, recovered, still_degraded}.
        """
        if not settings.recovery_enabled:
            logger.debug("Recovery disabled; skipping reconciliation")
            return {"scanned": 0, "rejoined": 0, "backfilled": 0, "recovered": 0, "still_degraded": 0}

        owns_session = db is None
        if owns_session:
            db = SessionLocal()

        summary = {
            "scanned": 0,
            "rejoined": 0,
            "backfilled": 0,
            "recovered": 0,
            "still_degraded": 0,
        }
        try:
            groups = (
                db.query(WhatsAppGroup)
                .filter(
                    WhatsAppGroup.is_active == True,  # noqa: E712
                    WhatsAppGroup.coverage_state.in_(
                        [
                            CoverageState.DEGRADED,
                            CoverageState.PAUSED,
                            CoverageState.RECOVERING,
                        ]
                    ),
                )
                .all()
            )

            for group in groups:
                summary["scanned"] += 1
                try:
                    await self._reconcile_group(group, db, summary)
                except Exception as exc:
                    logger.error("Recovery failed for %s: %s", group.group_jid, exc)
                    db.rollback()

            db.commit()
            logger.info(
                "Reconciliation complete: scanned=%(scanned)d rejoined=%(rejoined)d "
                "backfilled=%(backfilled)d recovered=%(recovered)d still_degraded=%(still_degraded)d",
                summary,
            )
            return summary
        except Exception as exc:
            logger.error("Reconciliation run failed: %s", exc)
            db.rollback()
            return summary
        finally:
            if owns_session and db is not None:
                db.close()

    async def _reconcile_group(
        self, group: WhatsAppGroup, db: Session, summary: Dict[str, int]
    ) -> None:
        """Reconcile a single group: re-join if needed, backfill, transition state."""
        group_jid = group.group_jid

        # PAUSED -> attempt rejoin, then move to RECOVERING for backfill.
        if group.coverage_state == CoverageState.PAUSED:
            rejoin = await self.service.rejoin_group(group_jid)
            if rejoin is None or not rejoin.get("ok", False):
                logger.info("Re-join not yet possible for %s; staying PAUSED", group_jid)
                return
            summary["rejoined"] += 1
            group.coverage_state = CoverageState.RECOVERING
            group.last_coverage_update = datetime.utcnow()
            db.commit()

        # Confirm bot membership before declaring recovery.
        membership = await self.service.is_bot_member(group_jid)
        if membership is False:
            logger.info("Bot still not a member of %s; staying PAUSED", group_jid)
            group.coverage_state = CoverageState.PAUSED
            group.last_coverage_update = datetime.utcnow()
            db.commit()
            return
        if membership is None:
            # Connector unreachable -> cannot confirm; leave state, count as degraded.
            summary["still_degraded"] += 1
            if group.coverage_state == CoverageState.ACTIVE:
                group.coverage_state = CoverageState.DEGRADED
                group.last_coverage_update = datetime.utcnow()
                if not group.outage_start:
                    group.outage_start = datetime.utcnow()
                db.commit()
            return

        # Bot is a member -> backfill any messages missed during the outage.
        backfilled = await self._backfill_group(group, db)
        summary["backfilled"] += backfilled

        # Restore ACTIVE coverage and close the outage window.
        if group.coverage_state != CoverageState.ACTIVE:
            group.coverage_state = CoverageState.ACTIVE
            group.last_coverage_update = datetime.utcnow()
            group.outage_end = datetime.utcnow()
            summary["recovered"] += 1
            db.commit()
            logger.info("Group %s recovered to ACTIVE", group_jid)

    async def _backfill_group(self, group: WhatsAppGroup, db: Session) -> int:
        """
        Re-ingest messages missed since the outage start (or the last checkpoint).
        Idempotent: already-stored messages are skipped via message_id dedup.
        """
        since_marker = self.listener._latest_message_marker(group.id, db)
        # Prefer the outage timestamp as the backfill start when available so we
        # explicitly cover the gap; otherwise resume from the last stored message.
        since = since_marker
        if group.outage_start and (not since or self._iso(group.outage_start) < since):
            since = self._iso(group.outage_start)

        messages = await self.service.fetch_messages(
            group.group_jid, since=since, limit=settings.recovery_backfill_limit
        )
        if messages is None:
            logger.info("Backfill unavailable for %s (connector unreachable)", group.group_jid)
            return 0

        ingested = 0
        for msg in messages:
            try:
                if self.listener.ingest_message(group, msg, db):
                    ingested += 1
            except Exception as exc:
                logger.error("Backfill ingest failed for %s: %s", group.group_jid, exc)
                db.rollback()
        if ingested:
            logger.info("Backfilled %d message(s) for %s", ingested, group.group_jid)
        return ingested

    @staticmethod
    def _iso(dt: datetime) -> str:
        return dt.astimezone().isoformat() if dt.tzinfo else dt.isoformat()
