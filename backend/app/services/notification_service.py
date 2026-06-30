"""
Notification delivery service
"""
import logging
from sqlalchemy.orm import Session
from app.models import NotificationInbox, User, AcademicEvent

logger = logging.getLogger(__name__)


class NotificationService:
    """Service to handle notification deliveries across different channels"""

    @staticmethod
    def send_event_notification(
        user: User,
        event: AcademicEvent,
        delivery_channel: str,
        db: Session
    ) -> bool:
        """Sends an event notification to the user and records it in the database inbox"""
        try:
            notification = NotificationInbox(
                user_id=user.id,
                event_id=event.id,
                notification_type="EVENT_REMINDER",
                title=f"Reminder: {event.title}",
                description=event.description or f"Reminder for {event.title}",
                is_read=False
            )
            db.add(notification)
            db.commit()
            logger.info(f"Notification recorded for user {user.id} via {delivery_channel}")
            return True
        except Exception as e:
            logger.error(f"Failed to record/send notification: {e}")
            if db:
                db.rollback()
            return False
