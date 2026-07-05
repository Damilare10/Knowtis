"""
Calendar Integration Service
Handles Google Calendar and Outlook sync for academic events.
"""
import logging
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import httpx
from sqlalchemy.orm import Session
from app.models import CalendarSync, AcademicEvent, EventType, User

logger = logging.getLogger(__name__)


class CalendarService:
    """Service for syncing academic events to external calendars"""

    GOOGLE_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{cal_id}/events"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    OUTLOOK_GRAPH_URL = "https://graph.microsoft.com/v1.0/me/events"

    # ── Google Calendar ───────────────────────────────────────────────────────

    @staticmethod
    def sync_to_google(user: User, db: Session) -> dict:
        """
        Push DEADLINE and EVENT academic events to Google Calendar.
        Requires a CalendarSync record with a valid access token.
        """
        sync_record = db.query(CalendarSync).filter(
            CalendarSync.user_id == user.id,
            CalendarSync.calendar_provider == "google",
            CalendarSync.is_active == True,
        ).first()

        if not sync_record:
            return {"success": False, "error": "No active Google Calendar connection found."}

        # Refresh token if expired
        if sync_record.token_expires_at and datetime.utcnow() > sync_record.token_expires_at:
            refreshed = CalendarService._refresh_google_token(sync_record, db)
            if not refreshed:
                return {"success": False, "error": "Google access token expired and refresh failed."}

        # Fetch events to sync (DEADLINE + EVENT types with a date)
        events = db.query(AcademicEvent).filter(
            AcademicEvent.user_id == user.id,
            AcademicEvent.is_archived == False,
            AcademicEvent.is_duplicate == False,
            AcademicEvent.event_type.in_([EventType.DEADLINE, EventType.EVENT]),
            AcademicEvent.date_time.isnot(None),
        ).all()

        synced = 0
        errors = []

        for event in events:
            try:
                CalendarService._push_event_to_google(event, sync_record.access_token, sync_record.calendar_id)
                synced += 1
            except Exception as e:
                logger.error(f"Failed to sync event {event.id} to Google: {e}")
                errors.append(str(event.id))

        sync_record.last_sync = datetime.utcnow()
        db.commit()

        return {
            "success": True,
            "provider": "google",
            "events_synced": synced,
            "errors": errors,
            "last_sync": sync_record.last_sync.isoformat(),
        }

    @staticmethod
    def _push_event_to_google(event: AcademicEvent, access_token: str, calendar_id: str):
        """Push a single academic event to Google Calendar via REST API."""
        dt = event.date_time.replace(tzinfo=timezone.utc)
        body = {
            "summary": event.title,
            "description": event.description or "",
            "location": event.venue or "",
            "start": {"dateTime": dt.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": dt.isoformat(), "timeZone": "UTC"},
        }

        url = CalendarService.GOOGLE_EVENTS_URL.format(cal_id=calendar_id or "primary")
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                url,
                json=body,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )
        if response.status_code not in (200, 201):
            raise Exception(f"Google Calendar API error: {response.status_code}")

    @staticmethod
    def _refresh_google_token(sync_record: CalendarSync, db: Session) -> bool:
        """Attempt to refresh an expired Google access token using the refresh token."""
        if not sync_record.refresh_token:
            return False

        from app.config import settings

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    CalendarService.GOOGLE_TOKEN_URL,
                    data={
                        "client_id": settings.google_client_id or "",
                        "client_secret": settings.google_client_secret or "",
                        "refresh_token": sync_record.refresh_token,
                        "grant_type": "refresh_token",
                    },
                )
                response.raise_for_status()
                tokens = response.json()

            sync_record.access_token = tokens["access_token"]
            sync_record.token_expires_at = datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600))
            db.commit()
            return True

        except Exception as e:
            logger.error(f"Google token refresh failed: {e}")
            return False

    # ── Outlook Calendar ──────────────────────────────────────────────────────

    @staticmethod
    def sync_to_outlook(user: User, db: Session) -> dict:
        """
        Push events to Microsoft Outlook Calendar via Graph API.
        Requires a CalendarSync record with a valid Graph access token.
        """
        sync_record = db.query(CalendarSync).filter(
            CalendarSync.user_id == user.id,
            CalendarSync.calendar_provider == "outlook",
            CalendarSync.is_active == True,
        ).first()

        if not sync_record:
            return {"success": False, "error": "No active Outlook Calendar connection found."}

        events = db.query(AcademicEvent).filter(
            AcademicEvent.user_id == user.id,
            AcademicEvent.is_archived == False,
            AcademicEvent.is_duplicate == False,
            AcademicEvent.event_type.in_([EventType.DEADLINE, EventType.EVENT]),
            AcademicEvent.date_time.isnot(None),
        ).all()

        synced = 0
        errors = []

        for event in events:
            try:
                CalendarService._push_event_to_outlook(event, sync_record.access_token)
                synced += 1
            except Exception as e:
                logger.error(f"Failed to sync event {event.id} to Outlook: {e}")
                errors.append(str(event.id))

        sync_record.last_sync = datetime.utcnow()
        db.commit()

        return {
            "success": True,
            "provider": "outlook",
            "events_synced": synced,
            "errors": errors,
            "last_sync": sync_record.last_sync.isoformat(),
        }

    @staticmethod
    def _push_event_to_outlook(event: AcademicEvent, access_token: str):
        """Push a single event to Outlook via Microsoft Graph API."""
        dt = event.date_time.replace(tzinfo=timezone.utc)
        body = {
            "subject": event.title,
            "body": {"contentType": "Text", "content": event.description or ""},
            "location": {"displayName": event.venue or ""},
            "start": {"dateTime": dt.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": dt.isoformat(), "timeZone": "UTC"},
        }

        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                CalendarService.OUTLOOK_GRAPH_URL,
                json=body,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )
        if response.status_code not in (200, 201):
            raise Exception(f"Graph API error: {response.status_code}")
