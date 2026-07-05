"""
Notification delivery service.

Beyond writing rows to the in-app inbox (``NotificationInbox``), this service
also:

* broadcasts every notification to live dashboard clients through the
  in-process realtime registry (``app.realtime.manager``), and
* dispatches *premium real-time alerts* through a pluggable push/DM channel
  abstraction (currently a webhook push channel) — including urgent
  timeline-shift alerts generated when a reminder/event's scheduled time
  changes.

``dispatch_alert`` is the entrypoint used by the reminder service and the
scheduler for premium real-time alerts.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models import AcademicEvent, NotificationInbox, User
from app.realtime import manager

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Push / DM channel abstraction
# --------------------------------------------------------------------------- #
class PushChannel:
    """Abstract push/DM channel for premium real-time alerts."""

    name = "base"

    async def send(self, user_id, payload: dict) -> bool:
        raise NotImplementedError


class WebhookPushChannel(PushChannel):
    """Push channel that POSTs alerts to a user-configured webhook URL.

    The URL is configured via the ``PUSH_WEBHOOK_URL`` environment variable
    (see ``app.config.settings.push_webhook_url``).
    """

    name = "webhook"

    def __init__(self, url: str, timeout_seconds: float = 5.0):
        self.url = url
        self.timeout_seconds = timeout_seconds

    async def send(self, user_id, payload: dict) -> bool:
        if not self.url:
            return False
        try:
            import httpx

            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    self.url,
                    json={
                        "user_id": str(user_id),
                        "channel": self.name,
                        "sent_at": datetime.utcnow().isoformat() + "Z",
                        "payload": payload,
                    },
                )
                ok = response.status_code < 400
                if not ok:
                    logger.warning(
                        "Webhook push returned %s for user %s",
                        response.status_code,
                        user_id,
                    )
                return ok
        except Exception as exc:
            logger.error("Webhook push failed for user %s: %s", user_id, exc)
            return False



_firebase_initialized = False

def initialize_firebase():
    global _firebase_initialized
    if _firebase_initialized:
        return
    import firebase_admin
    from firebase_admin import credentials
    import os
    import json
    
    cred_json = settings.firebase_credentials_json
    if not cred_json:
        logger.warning("Firebase credentials JSON not found in settings. Cannot initialize Firebase Admin.")
        return
        
    try:
        # Check if credentials JSON is a file path or raw JSON content
        if os.path.exists(cred_json):
            cred = credentials.Certificate(cred_json)
        else:
            # Parse it as raw JSON
            cred_dict = json.loads(cred_json)
            cred = credentials.Certificate(cred_dict)
            
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        logger.info("Firebase Admin successfully initialized.")
    except Exception as e:
        logger.error(f"Error initializing Firebase Admin: {e}")


class FCMPushChannel(PushChannel):
    """Push channel that routes notifications to Google Firebase Cloud Messaging (FCM)."""

    name = "firebase"

    def __init__(self):
        initialize_firebase()

    async def send(self, user_id, payload: dict) -> bool:
        if not _firebase_initialized:
            logger.warning("FCM send failed: Firebase Admin not initialized.")
            return False
            
        from app.database import SessionLocal
        from app.models import User
        
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.fcm_token:
                logger.debug(f"Skipping FCM push: user {user_id} has no registered fcm_token.")
                return False
                
            from firebase_admin import messaging
            import asyncio
            
            # Extract basic title and body from the payload
            title = payload.get("title") or "Knowtis Alert"
            body = payload.get("description") or ""
            
            # Map standard payload fields into custom string data dictionary for the client
            custom_data = {
                "event_id": str(payload.get("event_id")) if payload.get("event_id") else "",
                "notification_type": payload.get("notification_type") or "",
                "alert_level": payload.get("alert_level") or "info",
                "is_urgent": str(payload.get("is_urgent", False)).lower()
            }
            
            # Construct the messaging Message
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=custom_data,
                token=user.fcm_token
            )
            
            # Send message asynchronously in the executor thread
            response = await asyncio.to_thread(messaging.send, message)
            logger.info(f"FCM push notification successfully sent to user {user_id}: {response}")
            return True
            
        except Exception as e:
            logger.error(f"FCM push failed for user {user_id}: {e}")
            return False
        finally:
            db.close()


def get_push_channels() -> List[PushChannel]:
    """Build the list of enabled push channels from configuration."""
    channels: List[PushChannel] = []
    if settings.push_webhook_enabled and settings.push_webhook_url:
        channels.append(
            WebhookPushChannel(
                url=settings.push_webhook_url,
                timeout_seconds=settings.push_webhook_timeout_seconds,
            )
        )
    if settings.firebase_enabled():
        channels.append(FCMPushChannel())
    return channels


# --------------------------------------------------------------------------- #
# Timeline-shift detection
# --------------------------------------------------------------------------- #
def detect_timeline_shift(
    old_time: Optional[datetime],
    new_time: Optional[datetime],
    threshold_minutes: Optional[float] = None,
) -> Optional[timedelta]:
    """Return the signed shift delta when a scheduled time moved beyond threshold.

    Returns ``None`` when there is no meaningful shift (either time missing or
    the absolute change is below ``threshold_minutes``).
    """
    if old_time is None or new_time is None:
        return None
    if threshold_minutes is None:
        threshold_minutes = settings.timeline_shift_threshold_minutes
    delta = new_time - old_time
    if abs(delta.total_seconds()) < threshold_minutes * 60:
        return None
    return delta


def _humanize_delta(delta: timedelta) -> str:
    total_minutes = int(abs(delta.total_seconds()) // 60)
    hours, minutes = divmod(total_minutes, 60)
    if hours:
        return f"{hours}h{minutes}m"
    return f"{minutes}m"


# --------------------------------------------------------------------------- #
# Service
# --------------------------------------------------------------------------- #
class NotificationService:
    """Service handling notification delivery across inbox + realtime + push."""

    # -- core dispatch (DB write + live socket broadcast) -------------------- #
    @staticmethod
    def dispatch(
        user_id,
        notification_type: str,
        title: str,
        description: str,
        db: Session,
        event_id=None,
        alert_level: str = "info",
        is_urgent: bool = False,
    ) -> Optional[NotificationInbox]:
        """Persist a notification to the inbox and push it to live sockets.

        This is the single hook through which DB writes also fan out to live
        dashboard clients via the realtime registry.
        """
        notification = None
        try:
            notification = NotificationInbox(
                user_id=user_id,
                event_id=event_id,
                notification_type=notification_type,
                title=title,
                description=description,
                is_read=False,
            )
            db.add(notification)
            db.commit()
            db.refresh(notification)
        except Exception as exc:
            logger.error("Failed to record notification: %s", exc)
            if db:
                db.rollback()
            return None

        try:
            manager.broadcast_sync(
                user_id,
                {
                    "type": "notification",
                    "notification_type": notification_type,
                    "alert_level": alert_level,
                    "is_urgent": is_urgent,
                    "title": title,
                    "description": description,
                    "event_id": str(event_id) if event_id else None,
                    "id": str(notification.id),
                    "created_at": notification.created_at.isoformat()
                    if notification.created_at
                    else None,
                },
            )
        except Exception as exc:
            logger.debug("Realtime broadcast failed: %s", exc)

        logger.info(
            "Notification dispatched to user %s (%s)", user_id, notification_type
        )
        return notification

    # -- existing event notification (now wired through dispatch) ------------ #
    @staticmethod
    def send_event_notification(
        user: User,
        event: AcademicEvent,
        delivery_channel: str,
        db: Session,
    ) -> bool:
        """Record an event reminder notification and push it to live clients."""
        # Format a peer-like reminder description dynamically
        event_time_str = ""
        if event.date_time:
            now = datetime.utcnow()
            diff = event.date_time.date() - now.date()
            if diff.days == 0:
                day_part = "today"
            elif diff.days == 1:
                day_part = "tomorrow"
            else:
                day_part = event.date_time.strftime("%A")
                
            time_part = event.date_time.strftime("%I:%M %p").lower().lstrip("0")
            if time_part.endswith(":00 am"):
                time_part = time_part.replace(":00 am", "am")
            elif time_part.endswith(":00 pm"):
                time_part = time_part.replace(":00 pm", "pm")
            elif time_part.endswith(" am"):
                time_part = time_part.replace(" am", "am")
            elif time_part.endswith(" pm"):
                time_part = time_part.replace(" pm", "pm")
                
            event_time_str = f"{day_part} {time_part}"

        course_part = f"{event.course_code} " if event.course_code else ""
        venue_part = f" at {event.venue}" if event.venue else ""
        time_suffix = f" {event_time_str}" if event_time_str else ""
        
        peer_description = f"{course_part}{event.title}{time_suffix}{venue_part}".strip()

        notification = NotificationService.dispatch(
            user_id=user.id,
            notification_type="EVENT_REMINDER",
            title=f"Reminder: {event.title}",
            description=peer_description,
            db=db,
            event_id=event.id,
            alert_level="info",
        )
        if notification is None:
            return False
        logger.info(
            "Event notification recorded for user %s via %s",
            user.id,
            delivery_channel,
        )
        return True

    # -- premium real-time alert entrypoint --------------------------------- #
    @staticmethod
    def dispatch_alert(
        user_id,
        title: str,
        description: str,
        db: Session,
        event_id=None,
        alert_level: str = "urgent",
        push: bool = True,
    ) -> Optional[NotificationInbox]:
        """Entrypoint for premium real-time alerts.

        Writes an urgent inbox row, broadcasts to live sockets, and routes the
        alert through every enabled push/DM channel (e.g. webhook). Used by the
        reminder service and the scheduler.
        """
        notification = NotificationService.dispatch(
            user_id=user_id,
            notification_type="ALERT",
            title=title,
            description=description,
            db=db,
            event_id=event_id,
            alert_level=alert_level,
            is_urgent=True,
        )

        if push:
            payload = {
                "type": "alert",
                "alert_level": alert_level,
                "title": title,
                "description": description,
                "event_id": str(event_id) if event_id else None,
                "notification_id": str(notification.id) if notification else None,
                "created_at": datetime.utcnow().isoformat() + "Z",
            }
            NotificationService._schedule_push(user_id, payload)

        return notification

    @staticmethod
    def _schedule_push(user_id, payload: dict) -> None:
        """Fire-and-forget routing of an alert through all push channels."""
        channels = get_push_channels()
        if not channels:
            return

        async def _push() -> None:
            for channel in channels:
                try:
                    await channel.send(user_id, payload)
                except Exception as exc:
                    logger.error("Push channel %s failed: %s", channel.name, exc)

        loop = manager.loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(asyncio.ensure_future, _push())
        else:
            # No running loop (e.g. CLI / tests): run synchronously, best-effort.
            try:
                asyncio.run(_push())
            except Exception as exc:
                logger.debug("Push without a running loop failed: %s", exc)

    # -- timeline-shift alert ----------------------------------------------- #
    @staticmethod
    def notify_timeline_shift(
        user_id,
        event: AcademicEvent,
        old_scheduled_time: Optional[datetime],
        new_scheduled_time: Optional[datetime],
        db: Session,
    ) -> Optional[NotificationInbox]:
        """Generate an urgent alert when an event/reminder time shifts.

        When the scheduled time of a reminder/event changes beyond the
        configured threshold, an urgent alert is generated and routed through
        the push channel via :meth:`dispatch_alert`.
        """
        delta = detect_timeline_shift(old_scheduled_time, new_scheduled_time)
        if delta is None:
            return None

        direction = "moved earlier" if delta.total_seconds() < 0 else "moved later"
        human = _humanize_delta(delta)
        title = f"Schedule changed: {event.title}"
        description = (
            f"'{event.title}' {direction} by {human}. "
            f"New time: {new_scheduled_time.isoformat()}."
        )
        logger.info(
            "Timeline shift detected for event %s (%s by %s)",
            event.id,
            direction,
            human,
        )
        return NotificationService.dispatch_alert(
            user_id=user_id,
            title=title,
            description=description,
            db=db,
            event_id=event.id,
            alert_level="urgent",
            push=True,
        )

    # -- system-level messages (used by listener/recovery) ---------------- #
    @staticmethod
    def send_system_message(
        user_id,
        title: str,
        description: str,
        db: Session,
        event_id=None,
    ) -> Optional[NotificationInbox]:
        """Persist a generic system notification and broadcast it to live clients.

        No push-channel delivery — system messages stay inside the inbox/web feed
        to keep students informed about coverage gaps, recoveries, and other
        platform-level events.
        """
        return NotificationService.dispatch(
            user_id=user_id,
            notification_type="SYSTEM",
            title=title,
            description=description,
            db=db,
            event_id=event_id,
            alert_level="info",
            is_urgent=False,
        )
