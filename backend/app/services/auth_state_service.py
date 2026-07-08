"""
WhatsApp Auth State Service

Persist the full Baileys auth state to PostgreSQL so the WhatsApp connector
survives Render free-tier restarts and sleep/wake cycles.

The connector POSTs the serialized auth object (from Baileys `creds.update`
event) to the backend which stores it as JSONB in a single-row table.
On startup the connector GETs the latest state from the same endpoint and
feeds it to `makeWASocket`.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models import WhatsAppAuthState

logger = logging.getLogger(__name__)


def save_auth_state(db: Session, state: dict) -> None:
    """Save (upsert) the full Baileys auth state object."""
    row = (
        db.query(WhatsAppAuthState)
        .filter(WhatsAppAuthState.id == 1)
        .first()
    )

    if row:
        row.state = state
        row.last_updated = datetime.utcnow()
    else:
        row = WhatsAppAuthState(id=1, state=state, last_updated=datetime.utcnow())
        db.add(row)

    db.commit()
    logger.info("WhatsApp auth state saved (%d keys)", len(state or {}))


def load_auth_state(db: Session) -> Optional[dict]:
    """Load the latest Baileys auth state object, or None if not yet set."""
    row = (
        db.query(WhatsAppAuthState)
        .filter(WhatsAppAuthState.id == 1)
        .first()
    )
    return row.state if row and row.state else None
