"""
Reminder Scheduling Service
"""

import logging
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import Reminder, AcademicEvent, EventType
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class ReminderService:
    """Service for managing reminder scheduling and execution"""

    @staticmethod
    def create_reminder(
        user_id,
        event_id,
        reminder_type: str = "NOTIFICATION",
        delivery_channel: str = "IN_APP",
        days_before: int = 1,
        db: Session = None,
    ) -> Optional[Reminder]:
        """Create a reminder for an event"""
        try:
            event = db.query(AcademicEvent).filter(
                AcademicEvent.id == event_id,
                AcademicEvent.user_id == user_id,
            ).first()

            if not event or not event.date_time:
                logger.warning(f"Event not found or has no date_time: {event_id}")
                return None

            # Calculate reminder time
            reminder_time = event.date_time - timedelta(days=days_before)

            event = db.query(AcademicEvent).filter(
                AcademicEvent.id == event_id,
                AcademicEvent.user_id == user_id,
            ).first()
            if not event:
                logger.warning("Recurring reminder event not found or not owned: %s", event_id)
                return None

            reminder = Reminder(
                user_id=user_id,
                event_id=event_id,
                reminder_type=reminder_type,
                delivery_channel=delivery_channel,
                scheduled_time=reminder_time,
                is_active=True,
            )

            db.add(reminder)
            db.commit()
            db.refresh(reminder)

            logger.info(f"Reminder created: {reminder.id}")
            return reminder

        except Exception as e:
            logger.error(f"Error creating reminder: {e}")
            if db:
                db.rollback()
            return None

    @staticmethod
    def get_pending_reminders(db: Session = None) -> List[Reminder]:
        """Get all pending reminders that should be sent"""
        try:
            now = datetime.utcnow()

            reminders = db.query(Reminder).filter(
                Reminder.is_active == True,
                Reminder.is_sent == False,
                Reminder.scheduled_time <= now,
            ).all()

            return reminders

        except Exception as e:
            logger.error(f"Error getting pending reminders: {e}")
            return []

    @staticmethod
    def execute_reminder(reminder: Reminder, db: Session = None) -> bool:
        """Execute/send a reminder"""
        try:
            event = db.query(AcademicEvent).filter(
                AcademicEvent.id == reminder.event_id
            ).first()

            if not event:
                logger.warning(f"Event not found: {reminder.event_id}")
                return False

            user = event.user
            if not user:
                logger.warning(f"User not found: {event.user_id}")
                return False

            # Send notification
            NotificationService.send_event_notification(
                user=user,
                event=event,
                delivery_channel=reminder.delivery_channel,
                db=db,
            )

            # Mark reminder as sent
            reminder.is_sent = True
            reminder.sent_at = datetime.utcnow()
            db.commit()

            logger.info(f"Reminder executed: {reminder.id}")
            return True

        except Exception as e:
            logger.error(f"Error executing reminder: {e}")
            if db:
                db.rollback()
            return False

    @staticmethod
    def create_recurring_reminder(
        user_id,
        event_id,
        reminder_type: str,
        delivery_channel: str,
        recurrence_pattern: str,  # "daily", "weekly", etc.
        db: Session = None,
    ) -> Optional[Reminder]:
        """Create a recurring reminder"""
        try:
            reminder = Reminder(
                user_id=user_id,
                event_id=event_id,
                reminder_type=reminder_type,
                delivery_channel=delivery_channel,
                is_recurring=True,
                recurrence_pattern=recurrence_pattern,
                is_active=True,
            )

            db.add(reminder)
            db.commit()
            db.refresh(reminder)

            logger.info(f"Recurring reminder created: {reminder.id}")
            return reminder

        except Exception as e:
            logger.error(f"Error creating recurring reminder: {e}")
            if db:
                db.rollback()
            return None

    @staticmethod
    def dismiss_reminder(reminder_id, db: Session = None) -> bool:
        """Dismiss a reminder"""
        try:
            reminder = db.query(Reminder).filter(
                Reminder.id == reminder_id
            ).first()

            if reminder:
                reminder.is_active = False
                db.commit()
                logger.info(f"Reminder dismissed: {reminder_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error dismissing reminder: {e}")
            if db:
                db.rollback()
            return False

    @staticmethod
    def get_user_reminders(
        user_id,
        active_only: bool = True,
        limit: int = 50,
        db: Session = None,
    ) -> List[Reminder]:
        """Get reminders for a user"""
        try:
            query = db.query(Reminder).filter(
                Reminder.user_id == user_id
            )

            if active_only:
                query = query.filter(Reminder.is_active == True)

            reminders = query.order_by(
                Reminder.scheduled_time.desc()
            ).limit(limit).all()

            return reminders

        except Exception as e:
            logger.error(f"Error getting user reminders: {e}")
            return []

    @staticmethod
    def schedule_automatic_reminders(event: AcademicEvent, db: Session) -> List[Reminder]:
        """
        Dynamically schedule reminders for a newly created event based on its
        type and urgency score, rather than using fixed hardcoded offsets.
        """
        if not event or not event.date_time:
            return []

        # Real-time alerts are observational updates that should notify once
        # immediately when detected, not create future reminder rows.
        if event.event_type == EventType.ALERT:
            return []

        # Duplicate events should never generate their own reminder schedule.
        if getattr(event, "is_duplicate", False):
            return []

        now = datetime.utcnow()
        time_to_event = event.date_time - now

        # If the event is in the past, do not schedule reminders
        if time_to_event <= timedelta(0):
            return []

        offsets = []

        # High priority/urgent events (DEADLINE, ALERT, or urgency_score >= 0.8)
        if event.event_type in (EventType.DEADLINE, EventType.ALERT) or event.urgency_score >= 0.8:
            # 1. Preparation nudge (3 days before)
            if time_to_event > timedelta(days=4):
                offsets.append(timedelta(days=3))
            # 2. Final day nudge (24 hours before)
            if time_to_event > timedelta(days=1, hours=12):
                offsets.append(timedelta(days=1))
            # 3. Last chance nudge (3 hours before)
            if time_to_event > timedelta(hours=4):
                offsets.append(timedelta(hours=3))
        
        # Medium priority events (urgency_score between 0.5 and 0.8)
        elif event.urgency_score >= 0.5:
            # 1. Day before nudge (12 hours before)
            if time_to_event > timedelta(hours=14):
                offsets.append(timedelta(hours=12))
            # 2. Final hours nudge (3 hours before)
            if time_to_event > timedelta(hours=4):
                offsets.append(timedelta(hours=3))
        
        # Low priority/informational events
        else:
            # 1. Final hours nudge (3 hours before)
            if time_to_event > timedelta(hours=4):
                offsets.append(timedelta(hours=3))

        # If we couldn't schedule any advance reminders (e.g., event starts very soon),
        # but the event is high priority and starts in more than 15 minutes, schedule an immediate reminder
        if not offsets and time_to_event > timedelta(minutes=15):
            offsets.append(timedelta(minutes=0))

        created_reminders = []
        for offset in offsets:
            scheduled_time = event.date_time - offset
            
            # Ensure scheduled time is in the future
            if scheduled_time <= now:
                continue

            # Check if this reminder already exists to prevent duplicate runs
            exists = db.query(Reminder).filter(
                Reminder.user_id == event.user_id,
                Reminder.event_id == event.id,
                Reminder.scheduled_time == scheduled_time
            ).first()

            if not exists:
                reminder = Reminder(
                    user_id=event.user_id,
                    event_id=event.id,
                    reminder_type="NOTIFICATION",
                    delivery_channel="IN_APP",
                    scheduled_time=scheduled_time,
                    is_active=True
                )
                db.add(reminder)
                created_reminders.append(reminder)

        if created_reminders:
            db.commit()
            for r in created_reminders:
                db.refresh(r)
                logger.info(f"Automatically scheduled reminder {r.id} for event {event.id} at {r.scheduled_time}")

        return created_reminders
