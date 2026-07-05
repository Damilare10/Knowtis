"""
WhatsApp Anti-Ban: Session Rotation & Worker Pick.

Rotates worker session identifiers on a configurable interval and randomly
selects a worker session per group join, so that join traffic does not always
originate from the same bot session. Sessions are persisted in the
``whatsapp_sessions`` table; when no session rows are available a stable
deterministic fallback derived from the configured pool size is used so the
flow remains functional in dev/test without seeded data.
"""
import hashlib
import logging
import random
from datetime import datetime, timedelta
from typing import List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


def _list_active_sessions(db) -> List[object]:
    """Return active WhatsAppSession rows, ordered by most recently created."""
    from app.models import WhatsAppSession
    try:
        return (
            db.query(WhatsAppSession)
            .filter(WhatsAppSession.session_status == "ACTIVE")
            .order_by(WhatsAppSession.created_at.asc())
            .all()
        )
    except Exception as exc:  # noqa: BLE001 - tolerate dev/test without the table populated
        logger.debug("Could not query whatsapp_sessions: %s", exc)
        return []


def _session_due_for_rotation(session) -> bool:
    """A session is due for rotation once it has been active longer than the interval."""
    if session is None or getattr(session, "created_at", None) is None:
        return True
    interval = timedelta(minutes=settings.whatsapp_session_rotation_interval_minutes)
    return datetime.utcnow() - session.created_at >= interval


def rotate_sessions(db) -> Optional[object]:
    """
    Rotate worker sessions.

    Marks the oldest active session as ROTATING (eligible for replacement) and
    returns the next active session to use. If the pool is empty, no-op and
    return None (callers fall back to a deterministic virtual session id).
    """
    sessions = _list_active_sessions(db)
    if not sessions:
        logger.debug("Session rotation: no active sessions found; skipping rotation.")
        return None

    rotated = None
    for session in sessions:
        if _session_due_for_rotation(session):
            session.session_status = "ROTATING"
            session.updated_at = datetime.utcnow()
            rotated = session
            logger.info(
                "Session rotation: marking session %s as ROTATING (active since %s).",
                getattr(session, "id", "?"), session.created_at,
            )

    db.commit()

    active = _list_active_sessions(db)
    return active[0] if active else None


def pick_worker_session_id(db, salt: str = "") -> str:
    """
    Randomized worker pick for a single group join.

    Selects a random active session from the pool; if none are persisted, a
    deterministic virtual session id is derived from the configured pool size
    and the supplied salt so traffic is still spread across a virtual pool.
    """
    sessions = _list_active_sessions(db)
    if sessions:
        chosen = random.choice(sessions)
        return str(getattr(chosen, "session_token", None) or chosen.id)

    pool_size = max(1, settings.whatsapp_worker_pool_size)
    virtual_index = random.randint(0, pool_size - 1)
    token = hashlib.sha256(f"virtual-session-{virtual_index}-{salt}".encode()).hexdigest()[:16]
    logger.debug("pick_worker_session_id: using virtual session index %s (pool=%s).", virtual_index, pool_size)
    return f"virtual:{token}"
