"""
Celery Application Initialization
Defines the Celery client instance for managing asynchronous task workers,
backed by Redis as both the message broker and the result backend.
"""
from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "knowtis_workers",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    # Execution mode: eager (synchronous) only in tests/local; production uses a real worker.
    task_always_eager=settings.celery_task_always_eager,
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Ensures task definitions are registered and auto-discovered by the worker.
    imports=["app.tasks"],
    # Tolerate a broker that is not yet reachable when the worker boots (e.g. Redis starting up).
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=None,
    # Fetch one task at a time so worker-side jitter / burst protection is effective.
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_track_started=True,
    result_expires=60 * 60 * 24,
)

# Optional Celery beat schedule. Start with:
#   celery -A app.celery_app beat -l info
# to drive periodic jobs through the worker instead of the in-process APScheduler.
celery_app.conf.beat_schedule = {
    "send-pending-reminders": {
        "task": "app.tasks.send_pending_reminders_task",
        "schedule": 300.0,
    },
    "send-night-brief": {
        "task": "app.tasks.send_night_brief_task",
        "schedule": crontab(hour=20, minute=0),
    },
    "process-pending-joins": {
        "task": "app.tasks.process_pending_joins_task",
        "schedule": 30.0,
    },
    # Drive the headless listener: poll active groups for new messages.
    "drive-whatsapp-listener": {
        "task": "app.tasks.drive_listener",
        "schedule": crontab(minute="*/2"),
    },
    # Self-initiated bot-removal / coverage detection.
    "detect-bot-removal": {
        "task": "app.tasks.detect_bot_removal",
        "schedule": crontab(minute="*/2"),
    },
    # Reconciliation & backfill for degraded/paused/recovering groups.
    "reconcile-groups": {
        "task": "app.tasks.recover_groups",
        "schedule": crontab(minute="*/5"),
    },
}
