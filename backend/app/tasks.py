"""
Celery Task Definitions
Contains all asynchronous background jobs for Knowtis workers.

All tasks inherit from :class:`RateLimitedTask`, which injects a randomized
jitter delay before the task body executes. This smooths out bursts of messages
arriving simultaneously and reduces the chance of WhatsApp anti-bot detection
when many groups send messages at once. The jitter is skipped automatically
when ``CELERY_TASK_ALWAYS_EAGER`` is True (tests / local dev without a worker).
"""
import logging
import json
import random
import time
import asyncio
import re
from datetime import datetime

from celery import Task

from app.celery_app import celery_app
from app.config import settings

logger = logging.getLogger(__name__)


CALENDAR_COMMAND_PHRASES = [
    "add this to my calendar",
    "add to my calendar",
    "add to calendar",
    "sync calendar",
]

GROUP_BROADCAST_TAGS = {
    "@all",
    "@everyone",
    "@here",
}


def _has_calendar_command(message_text: str) -> bool:
    text = (message_text or "").lower()
    return "calendar" in text and any(kw in text for kw in ["add", "sync"])


def _is_tagged_bot_command(data: dict) -> bool:
    message_text = data.get("message_text") or ""
    if not _has_calendar_command(message_text):
        return False

    if data.get("mention_all"):
        return False

    if data.get("is_bot_mentioned"):
        return True

    text_lower = message_text.lower()
    if any(tag in text_lower for tag in GROUP_BROADCAST_TAGS):
        return False

    # Backward-compatible fallback for older connector payloads that do not yet
    # include mention metadata.
    return "knowtis" in text_lower


def _strip_calendar_command_text(message_text: str) -> str:
    clean_msg = message_text or ""
    clean_msg = re.sub(r"@\S+", "", clean_msg)
    for pattern in [*CALENDAR_COMMAND_PHRASES, "calendar", "knowtis"]:
        clean_msg = re.sub(rf"(?i){re.escape(pattern)}", "", clean_msg)
    return clean_msg.strip(": \t\n\r")


def _run_async(coro):
    """Run a coroutine from a synchronous Celery task context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(lambda: asyncio.run(coro)).result()
    except RuntimeError:
        pass
    return asyncio.run(coro)


def apply_burst_delay(task_name: str) -> None:
    """
    Inject a randomized burst-protection delay before a task body runs.

    The delay is drawn uniformly from
    ``[WORKER_JITTER_MIN_SECONDS, WORKER_JITTER_MAX_SECONDS]``. It is skipped
    entirely when Celery is running in eager (synchronous) mode so that tests
    and local development remain fast and deterministic.
    """
    if settings.celery_task_always_eager:
        return
    lo = settings.worker_jitter_min_seconds
    hi = settings.worker_jitter_max_seconds
    if hi <= 0:
        return
    lo = max(0.0, lo)
    hi = max(lo, hi)
    delay = random.uniform(lo, hi)
    logger.debug("Burst protection: sleeping %.3fs before task %s", delay, task_name)
    time.sleep(delay)


class RateLimitedTask(Task):
    """
    Reusable Celery task base that applies worker-side burst protection.

    Override ``__call__`` (which Celery invokes on the worker when a custom
    ``__call__`` is present) to inject randomized jitter before delegating to
    the normal task body.
    """

    abstract = True

    def __call__(self, *args, **kwargs):
        apply_burst_delay(self.name)
        return super().__call__(*args, **kwargs)


@celery_app.task(name="app.tasks.process_incoming_message_task", base=RateLimitedTask)
def process_incoming_message_task(data: dict):
    """
    Asynchronously processes a WhatsApp message:
    1. Saves to RawMessage log.
    2. Runs message classification (Signal vs Noise).
    3. Runs event extraction on Signal messages.
    4. Triggers deduplication and persists academic events.
    5. Dispatches notifications.
    """
    from app.database import SessionLocal
    from app.models import WhatsAppGroup, RawMessage, AcademicEvent, CoverageState, User, EventType
    from app.services.classifier_service import MessageClassifier, Classification
    from app.services.event_extraction_service import EventExtractionService
    from app.services.deduplication_service import DeduplicationService
    from app.services.notification_service import NotificationService
    from app.services.reminder_service import ReminderService
    from app.services.training_feedback_service import TrainingFeedbackService
    from app.utils import generate_embedding

    group_jid = data.get("group_jid")
    message_id = data.get("message_id")
    sender_jid = data.get("sender_jid")
    sender_name = data.get("sender_name")
    message_text = data.get("message_text")

    if not group_jid or not message_text:
        logger.warning("Ignoring task execution: message payload is missing key details.")
        return "ignored_missing_data"

    db = SessionLocal()
    try:
        # Detect direct bot-tagged calendar command.
        if _is_tagged_bot_command(data):
            # Clean sender_jid to get numeric phone number digits
            sender_phone = (
                "".join(c for c in sender_jid.split("@")[0] if c.isdigit())
                if sender_jid
                else None
            )
            if sender_phone:
                # Find matching user
                sync_user = db.query(User).filter(User.whatsapp_number == sender_phone).first()
                if sync_user:
                    logger.info(f"Detected calendar command from user {sync_user.id} ({sender_phone})")
                    
                    # 1. Clean message text of tag/command to see if there is substantial event text
                    clean_msg = _strip_calendar_command_text(message_text)
                    
                    extracted = None
                    if len(clean_msg) > 10:
                        # Try to extract event details from remaining text
                        extracted = EventExtractionService.extract_event(clean_msg, db=db)
                    
                    # 2. If no event details in the message, fall back to the most recent event in the group JID
                    if not extracted:
                        recent_event = db.query(AcademicEvent).filter(
                            AcademicEvent.source_group_jid == group_jid,
                            AcademicEvent.is_duplicate == False
                        ).order_by(AcademicEvent.created_at.desc()).first()
                        
                        if recent_event:
                            extracted = {
                                "event_type": recent_event.event_type,
                                "course_code": recent_event.course_code,
                                "title": recent_event.title,
                                "description": recent_event.description,
                                "venue": recent_event.venue,
                                "date_time": recent_event.date_time,
                                "urgency_score": recent_event.urgency_score,
                                "confidence_score": recent_event.confidence_score,
                                "relevance_score": recent_event.relevance_score,
                                "actionability_score": recent_event.actionability_score,
                                "embedding": recent_event.embedding,
                                "source_message_id": recent_event.source_message_id,
                                "source_group_jid": recent_event.source_group_jid
                            }
                    
                    # 3. If we resolved an event (either from text or recent group event), save it
                    if extracted:
                        # Check if this user already has an event with the same source_message_id
                        existing_user_event = db.query(AcademicEvent).filter(
                            AcademicEvent.user_id == sync_user.id,
                            AcademicEvent.source_message_id == extracted.get("source_message_id")
                        ).first() if extracted.get("source_message_id") else None
                        
                        if not existing_user_event:
                            # Generate embedding if not already present
                            embedding_str = extracted.get("embedding")
                            if not embedding_str:
                                text_for_analysis = f"{extracted['title']} {extracted.get('description', '')} {extracted.get('course_code') or ''}"
                                embedding_str = json.dumps(generate_embedding(text_for_analysis))
                                
                            academic_event = AcademicEvent(
                                user_id=sync_user.id,
                                group_id=None,  # Imported personal event
                                event_type=extracted["event_type"],
                                course_code=extracted.get("course_code"),
                                title=extracted["title"],
                                description=extracted.get("description"),
                                venue=extracted.get("venue"),
                                date_time=extracted.get("date_time"),
                                urgency_score=extracted.get("urgency_score", 0.5),
                                confidence_score=extracted.get("confidence_score", 0.8),
                                relevance_score=extracted.get("relevance_score", 0.7),
                                actionability_score=extracted.get("actionability_score", 0.6),
                                embedding=embedding_str,
                                source_message_id=extracted.get("source_message_id") or message_id,
                                source_group_jid=extracted.get("source_group_jid") or group_jid,
                            )
                            db.add(academic_event)
                            db.commit()
                            db.refresh(academic_event)
                            
                            if not academic_event.is_duplicate:
                                # Observation/schedule-shift alerts notify once immediately.
                                if academic_event.event_type == EventType.ALERT:
                                    NotificationService.dispatch_alert(
                                        user_id=sync_user.id,
                                        title=f"Alert: {academic_event.title}",
                                        description=academic_event.description or academic_event.title,
                                        db=db,
                                        event_id=academic_event.id,
                                        alert_level="urgent",
                                        push=True,
                                    )
                                else:
                                    # Automatically schedule dynamic in-app reminders
                                    ReminderService.schedule_automatic_reminders(academic_event, db)

                                    # Dispatch in-app notification
                                    NotificationService.send_event_notification(
                                        sync_user,
                                        academic_event,
                                        "IN_APP",
                                        db
                                    )
                            logger.info(f"Successfully added event '{academic_event.title}' to user {sync_user.id}'s in-app calendar.")

        # Find all active groups monitoring this JID
        active_groups = db.query(WhatsAppGroup).filter(
            WhatsAppGroup.group_jid == group_jid,
            WhatsAppGroup.is_active == True
        ).all()

        if not active_groups:
            logger.info(f"Asynchronously ignored message in group {group_jid}: group is not monitored by any user.")
            return "ignored_group_not_monitored"

        processed_count = 0
        for group in active_groups:
            existing_raw = db.query(RawMessage.id).filter(
                RawMessage.group_id == group.id,
                RawMessage.message_id == message_id,
            ).first()
            if existing_raw:
                logger.info(
                    "Skipping duplicate webhook message %s for group %s",
                    message_id,
                    group.group_jid,
                )
                continue

            # 1. Save to RawMessage audit log
            raw = RawMessage(
                user_id=group.user_id,
                group_id=group.id,
                message_id=message_id,
                sender_jid=sender_jid,
                sender_name=sender_name,
                message_text=message_text,
                message_type="text",
                created_at=datetime.utcnow()
            )
            db.add(raw)
            db.commit()

            # 2. Classify message (Signal vs Noise)
            classification, conf = MessageClassifier.classify_message(message_text)
            raw.classification = classification.value
            raw.confidence_score = conf
            db.commit()

            if classification == Classification.SIGNAL:
                # 3. Extract event details
                event_data = EventExtractionService.extract_event(
                    message_text,
                    db=db,
                    msg_created_at=raw.created_at,
                )
                if event_data:
                    # 4. Check for duplicates
                    text_for_analysis = f"{event_data['title']} {event_data['description']} {event_data['course_code'] or ''}"
                    canonical = DeduplicationService.find_duplicate(
                        user_id=group.user_id,
                        new_event_text=text_for_analysis,
                        group_id=group.id,
                        db=db
                    )

                    is_duplicate = canonical is not None
                    canonical_id = canonical.id if canonical else None

                    # Generate embedding
                    embedding_str = json.dumps(generate_embedding(text_for_analysis))

                    # 5. Persist academic event
                    academic_event = AcademicEvent(
                        user_id=group.user_id,
                        group_id=group.id,
                        event_type=event_data["event_type"],
                        course_code=event_data["course_code"],
                        title=event_data["title"],
                        description=event_data["description"],
                        venue=event_data["venue"],
                        date_time=event_data["date_time"],
                        urgency_score=event_data["urgency_score"],
                        confidence_score=event_data["confidence_score"],
                        relevance_score=event_data["relevance_score"],
                        actionability_score=event_data["actionability_score"],
                        is_duplicate=is_duplicate,
                        canonical_event_id=canonical_id,
                        embedding=embedding_str,
                        source_message_id=message_id,
                        source_group_jid=group_jid,
                    )
                    db.add(academic_event)
                    db.flush()
                    TrainingFeedbackService.record_prediction(
                        db=db,
                        user_id=group.user_id,
                        message_text=message_text,
                        event_data=event_data,
                        raw_message_id=raw.id,
                        academic_event_id=academic_event.id,
                    )
                    db.commit()
                    db.refresh(academic_event)

                    if not academic_event.is_duplicate and not event_data.get("needs_review"):
                        if academic_event.event_type == EventType.ALERT:
                            NotificationService.dispatch_alert(
                                user_id=group.user.id,
                                title=f"Alert: {academic_event.title}",
                                description=academic_event.description or academic_event.title,
                                db=db,
                                event_id=academic_event.id,
                                alert_level="urgent",
                                push=True,
                            )
                        else:
                            # Automatically schedule dynamic in-app reminders
                            ReminderService.schedule_automatic_reminders(academic_event, db)

                            # 6. Send in-app notification
                            NotificationService.send_event_notification(group.user, academic_event, "IN_APP", db)
                    processed_count += 1

            raw.processing_status = "PROCESSED"
            db.commit()

            # Update coverage timestamp
            group.last_coverage_update = datetime.utcnow()
            db.commit()

        logger.info(f"Asynchronously processed message for {len(active_groups)} group(s). Extracted {processed_count} events.")
        return f"processed_{len(active_groups)}_groups_{processed_count}_signals"

    except Exception as e:
        logger.exception("Error in process_incoming_message_task")
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="app.tasks.send_pending_reminders_task", base=RateLimitedTask)
def send_pending_reminders_task():
    """Asynchronous task wrapper to execute due reminders"""
    from app.scheduler import _execute_pending_reminders
    _execute_pending_reminders()
    return "done"


@celery_app.task(name="app.tasks.send_night_brief_task", base=RateLimitedTask)
def send_night_brief_task():
    """Asynchronous task wrapper to generate daily night briefs"""
    from app.scheduler import _generate_night_briefs
    _generate_night_briefs()
    return "done"


@celery_app.task(name="app.tasks.process_pending_joins_task", base=RateLimitedTask)
def process_pending_joins_task():
    """Asynchronous task wrapper for staggered WhatsApp group joins (anti-ban)."""
    from app.scheduler import _process_pending_joins
    _process_pending_joins()
    return "done"


@celery_app.task(name="app.tasks.drive_listener", base=RateLimitedTask)
def drive_listener():
    """Poll all monitored groups and ingest new messages via the headless listener."""
    from app.services.whatsapp_listener_service import WhatsAppListenerService

    logger.info("Driving WhatsApp listener cycle")
    return _run_async(WhatsAppListenerService().run_listener_cycle())


@celery_app.task(name="app.tasks.detect_bot_removal", base=RateLimitedTask)
def detect_bot_removal():
    """Self-initiated bot-removal / coverage detection pass."""
    from app.services.whatsapp_listener_service import WhatsAppListenerService

    logger.info("Running bot-removal detection")
    return _run_async(WhatsAppListenerService().detect_bot_removal())


@celery_app.task(name="app.tasks.recover_groups", base=RateLimitedTask)
def recover_groups():
    """Reconcile degraded/paused/recovering groups and backfill missed messages."""
    from app.services.recovery_service import RecoveryService

    logger.info("Running group reconciliation")
    return _run_async(RecoveryService().reconcile_groups())
