"""
API Routes - Calendar Integration
Google Calendar and Outlook sync (Premium feature).
"""
import json
import logging
from datetime import datetime, timedelta
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, CalendarSync
from app.schemas import CalendarConnectRequest, CalendarStatusResponse
from app.dependencies import get_current_user, require_premium
from app.services.calendar_service import CalendarService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/calendar", tags=["Calendar"])

SUPPORTED_PROVIDERS = ("google", "outlook")


@router.get("/status", response_model=list[CalendarStatusResponse])
async def get_calendar_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the sync status of all connected calendars for this user"""
    syncs = db.query(CalendarSync).filter(
        CalendarSync.user_id == user.id,
        CalendarSync.is_active == True,
    ).all()

    return [
        {
            "provider": s.calendar_provider,
            "is_active": s.is_active,
            "last_sync": s.last_sync,
        }
        for s in syncs
    ]


@router.post("/connect", status_code=status.HTTP_201_CREATED)
async def connect_calendar(
    body: CalendarConnectRequest,
    user: User = Depends(require_premium),
    db: Session = Depends(get_db),
):
    """
    Connect a calendar provider using an OAuth auth code.
    Premium only. Supported providers: 'google', 'outlook'.
    """
    if body.provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported calendar provider. Choose from: {', '.join(SUPPORTED_PROVIDERS)}",
        )

    # Exchange auth code for tokens
    if body.provider == "google":
        tokens = _exchange_google_calendar_code(body.auth_code)
    else:
        tokens = _exchange_outlook_code(body.auth_code)

    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to exchange authorization code with {body.provider}.",
        )

    # Upsert CalendarSync record
    existing = db.query(CalendarSync).filter(
        CalendarSync.user_id == user.id,
        CalendarSync.calendar_provider == body.provider,
    ).first()

    if existing:
        existing.access_token = tokens["access_token"]
        existing.refresh_token = tokens.get("refresh_token", existing.refresh_token)
        existing.token_expires_at = tokens.get("expires_at")
        existing.is_active = True
    else:
        sync = CalendarSync(
            user_id=user.id,
            calendar_provider=body.provider,
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            token_expires_at=tokens.get("expires_at"),
            is_active=True,
        )
        db.add(sync)

    db.commit()
    return {"message": f"{body.provider.capitalize()} Calendar connected successfully."}


@router.post("/sync")
async def sync_calendar(
    user: User = Depends(require_premium),
    db: Session = Depends(get_db),
):
    """
    Trigger an immediate sync of all academic events to all connected calendars.
    Premium only.
    """
    syncs = db.query(CalendarSync).filter(
        CalendarSync.user_id == user.id,
        CalendarSync.is_active == True,
    ).all()

    if not syncs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No connected calendars found. Please connect a calendar first.",
        )

    results = []
    for sync in syncs:
        if sync.calendar_provider == "google":
            result = CalendarService.sync_to_google(user=user, db=db)
        elif sync.calendar_provider == "outlook":
            result = CalendarService.sync_to_outlook(user=user, db=db)
        else:
            result = {"provider": sync.calendar_provider, "success": False, "error": "Unknown provider"}

        results.append(result)

    return {"results": results}


@router.delete("/disconnect/{provider}")
async def disconnect_calendar(
    provider: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke and remove a calendar connection"""
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider. Choose from: {', '.join(SUPPORTED_PROVIDERS)}",
        )

    sync = db.query(CalendarSync).filter(
        CalendarSync.user_id == user.id,
        CalendarSync.calendar_provider == provider,
    ).first()

    if not sync:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {provider} calendar connection found.",
        )

    sync.is_active = False
    sync.access_token = ""
    sync.refresh_token = None
    db.commit()

    return {"message": f"{provider.capitalize()} Calendar disconnected."}


# ── OAuth helpers ─────────────────────────────────────────────────────────────

def _post_form(url: str, form: dict, timeout: float = 10.0) -> dict | None:
    """POST ``application/x-www-form-urlencoded`` via httpx and return JSON.

    Centralised so the rest of the calendar module can use httpx (already
    imported elsewhere) instead of mixing ``urllib.request`` blocking calls.
    """
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, data=form)
            response.raise_for_status()
            return response.json()
    except Exception as exc:
        logger.error("OAuth POST to %s failed: %s", url, exc)
        return None


def _exchange_google_calendar_code(code: str) -> dict | None:
    """Exchange a Google auth code for calendar access + refresh tokens."""
    if not settings.google_client_id or not settings.google_client_secret:
        logger.warning("Google credentials not configured")
        return None

    tokens = _post_form(
        "https://oauth2.googleapis.com/token",
        {
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": f"{settings.backend_url}/api/v1/calendar/callback/google",
            "grant_type": "authorization_code",
        },
    )
    if not tokens or "access_token" not in tokens:
        return None

    expires_at = datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600))
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token"),
        "expires_at": expires_at,
    }


def _exchange_outlook_code(code: str) -> dict | None:
    """Exchange a Microsoft auth code for calendar access + refresh tokens."""
    if not settings.outlook_client_id or not settings.outlook_client_secret:
        logger.warning("Outlook credentials not configured")
        return None

    tenant = "common"
    tokens = _post_form(
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        {
            "code": code,
            "client_id": settings.outlook_client_id,
            "client_secret": settings.outlook_client_secret,
            "redirect_uri": f"{settings.backend_url}/api/v1/calendar/callback/outlook",
            "grant_type": "authorization_code",
            "scope": "Calendars.ReadWrite offline_access",
        },
    )
    if not tokens or "access_token" not in tokens:
        return None

    expires_at = datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600))
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token"),
        "expires_at": expires_at,
    }
