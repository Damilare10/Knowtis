"""
Auth State Sync Endpoint

Unauthenticated endpoint for the WhatsApp connector to sync its Baileys
credentials to PostgreSQL. Protected by a shared secret passed in the
``X-Auth-State-Secret`` header.

Only the connector needs this — no auth middleware is required because
the secret acts as the authentication.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services import auth_state_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/whatsapp", tags=["WhatsApp"])


def _validate_auth_state_secret(header_value: Optional[str]) -> bool:
    """Validate the shared secret for auth state sync."""
    expected = getattr(settings, "whatsapp_connector_api_secret", "")
    if not expected:
        logger.warning("WHATSAPP_CONNECTOR_API_SECRET is not configured — rejecting auth state sync")
        return False
    import hmac
    return hmac.compare_digest(header_value or "", expected)


@router.post("/auth-state", include_in_schema=False)
async def sync_auth_state(
    state: dict,
    x_webhook_secret: Optional[str] = Header(default=None, alias="X-Webhook-Secret"),
    x_connector_secret: Optional[str] = Header(default=None, alias="X-Connector-Secret"),
    db: Session = Depends(get_db),
):
    """
    Receive and persist the Baileys auth state from the connector.

    The connector POSTs the full auth object on every `creds.update` event.
    The secret can be passed via either ``X-Webhook-Secret`` or
    ``X-Connector-Secret`` (they share the same value by default).

    An empty state `{}` is accepted — it clears any previously saved auth
    (used by the /reset endpoint to wipe credentials).
    """
    header_value = x_webhook_secret or x_connector_secret
    if not _validate_auth_state_secret(header_value):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid auth state secret.",
        )

    # Accept empty dict (reset) or non-empty state
    auth_state_service.save_auth_state(db, state if state else {})
    return {"status": "ok"}


@router.get("/auth-state", include_in_schema=False)
async def get_auth_state(
    x_webhook_secret: Optional[str] = Header(default=None, alias="X-Webhook-Secret"),
    x_connector_secret: Optional[str] = Header(default=None, alias="X-Connector-Secret"),
    db: Session = Depends(get_db),
):
    """
    Return the persisted Baileys auth state for the connector to use on startup.

    Returns an empty object when no state has been saved yet (fresh pair).
    The secret is validated the same way as the POST endpoint.
    """
    header_value = x_webhook_secret or x_connector_secret
    if not _validate_auth_state_secret(header_value):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid auth state secret.",
        )

    state = auth_state_service.load_auth_state(db)
    if state is None:
        return {"state": {}}

    return {"state": state}
