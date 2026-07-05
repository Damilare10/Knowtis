"""
Background Scheduler
Uses APScheduler to run periodic jobs inside the FastAPI process.
Handles: reminder execution, Night Brief generation, and staggered WhatsApp group joining.
"""
import logging
import random
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False
    logger.warning(
        "APScheduler not installed — background jobs disabled. "
        "Run: pip install apscheduler"
    )

_scheduler = None


def _execute_pending_reminders():
    """Job: fire all reminders that are due right now"""
    from app.database import SessionLocal
    from app.services.reminder_service import ReminderService

    db = SessionLocal()
    try:
        pending = ReminderService.get_pending_reminders(db=db)
        if not pending:
            return

        logger.info(f"Reminder job: executing {len(pending)} pending reminder(s)")
        for reminder in pending:
            ReminderService.execute_reminder(reminder=reminder, db=db)

    except Exception as e:
        logger.error(f"Reminder job error: {e}")
    finally:
        db.close()


def _generate_night_briefs():
    """
    Job: generate a Night Brief notification for every active user at 20:00 daily.
    Creates a notification_inbox record summarising tomorrow's deadlines.
    """
    from app.database import SessionLocal
    from app.models import User, AcademicEvent, NotificationInbox, EventType

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        tomorrow = now + timedelta(hours=24)

        users = db.query(User).filter(User.is_active == True).all()
        logger.info(f"Night Brief job: processing {len(users)} user(s)")

        for user in users:
            try:
                # Count upcoming deadlines
                deadlines = db.query(AcademicEvent).filter(
                    AcademicEvent.user_id == user.id,
                    AcademicEvent.is_archived == False,
                    AcademicEvent.is_duplicate == False,
                    AcademicEvent.event_type == EventType.DEADLINE,
                    AcademicEvent.date_time >= now,
                    AcademicEvent.date_time <= tomorrow,
                ).count()

                alerts = db.query(AcademicEvent).filter(
                    AcademicEvent.user_id == user.id,
                    AcademicEvent.is_archived == False,
                    AcademicEvent.event_type == EventType.ALERT,
                ).count()

                if deadlines == 0 and alerts == 0:
                    summary = "All clear for tomorrow. No urgent deadlines or alerts."
                else:
                    parts = []
                    if deadlines:
                        parts.append(f"{deadlines} deadline(s) coming up")
                    if alerts:
                        parts.append(f"{alerts} active alert(s)")
                    summary = "Night Brief: " + ", ".join(parts) + "."

                notification = NotificationInbox(
                    user_id=user.id,
                    notification_type="NIGHT_BRIEF",
                    title="Your Night Brief is Ready",
                    description=summary,
                    is_read=False,
                )
                db.add(notification)

            except Exception as e:
                logger.error(f"Night Brief error for user {user.id}: {e}")
                continue

        db.commit()
        logger.info("Night Brief job: completed")

    except Exception as e:
        logger.error(f"Night Brief job error: {e}")
    finally:
        db.close()


def _process_pending_joins():
    """
    Job: Staggered WhatsApp group joining.
    Processes one pending join at a time, enforcing at least 3 minutes between
    joins (plus a random jitter). Applies worker-side burst protection, rotates
    worker sessions on a configurable interval, and randomly picks a worker
    session per join to distribute anti-ban traffic across the pool.
    """
    from app.database import SessionLocal
    from app.models import WhatsAppGroup, CoverageState
    from app.services.whatsapp_service import WhatsAppService
    from app.tasks import apply_burst_delay
    from app.session_rotation import rotate_sessions, pick_worker_session_id

    # Worker-side randomized burst protection before touching the queue.
    apply_burst_delay("scheduler.process_pending_joins")

    db = SessionLocal()
    try:
        # Anti-ban: rotate worker sessions that have outlived their interval.
        rotate_sessions(db)

        # Query groups awaiting joining (JID starts with pending-)
        pending_groups = db.query(WhatsAppGroup).filter(
            WhatsAppGroup.group_jid.like("pending-%"),
            WhatsAppGroup.is_active == True
        ).order_by(WhatsAppGroup.created_at.asc()).all()

        if not pending_groups:
            return

        # Anti-ban protection: check when the last group join occurred
        last_joined = db.query(WhatsAppGroup).filter(
            ~WhatsAppGroup.group_jid.like("pending-%"),
            WhatsAppGroup.is_active == True
        ).order_by(WhatsAppGroup.join_date.desc()).first()

        # Enforce 3-minute staggered gap + random jitter (5 to 30 seconds)
        jitter = random.randint(5, 30)
        min_gap = timedelta(minutes=3) + timedelta(seconds=jitter)

        if last_joined and last_joined.join_date:
            elapsed = datetime.utcnow() - last_joined.join_date
            if elapsed < min_gap:
                logger.info(
                    f"Join queue: waiting to join. Elapsed since last join: {elapsed.total_seconds():.1f}s, "
                    f"Required gap (with jitter): {min_gap.total_seconds()}s"
                )
                return

        # Process the oldest pending group join request
        group_to_join = pending_groups[0]
        # JID format: pending-{invite_code}@g.us
        invite_code = group_to_join.group_jid.split("@")[0].replace("pending-", "")
        invite_link = f"https://chat.whatsapp.com/{invite_code}"

        # Anti-ban: randomize which worker session performs this join.
        session_id = pick_worker_session_id(db, salt=invite_code)

        logger.info(
            f"Join queue: attempting to join group with invite code '{invite_code}' via session '{session_id}'"
        )
        res = WhatsAppService.join_group(invite_link=invite_link, session_id=session_id)

        if res.get("success"):
            # Update all pending records for this invite code in case multiple users linked the same group
            matching_pending = db.query(WhatsAppGroup).filter(
                WhatsAppGroup.group_jid == group_to_join.group_jid
            ).all()

            for g in matching_pending:
                g.group_jid = res["group_jid"]
                g.group_name = res["group_name"]
                g.coverage_state = CoverageState.ACTIVE
                g.join_date = datetime.utcnow()
                g.last_coverage_update = datetime.utcnow()

            db.commit()
            logger.info(f"Join queue: successfully joined group JID {res['group_jid']} for {len(matching_pending)} records")
        else:
            logger.warning(f"Join queue: failed to join group '{invite_code}': {res.get('message')}")
            # If the join fails due to a bad link or other reasons, we keep it pending so it retries,
            # but in production we'd want to set a limit or flag invalid links to avoid infinite loops.

    except Exception as e:
        logger.error(f"Join queue job error: {e}")
    finally:
        db.close()


def start_scheduler():
    """
    Start the background scheduler.
    Jobs:
    - Every 5 minutes: execute due reminders
    - Daily at 20:00 UTC: generate Night Briefs for all users
    - Every 30 seconds: process staggered WhatsApp group joins
    """
    global _scheduler

    if not HAS_APSCHEDULER:
        logger.warning("APScheduler not available — skipping scheduler startup")
        return

    from app.config import settings

    # Disabled by default outside production so local dev/reload does not spawn
    # duplicate DB/WhatsApp polling jobs. Set SCHEDULER_ENABLED=true to opt in.
    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled via SCHEDULER_ENABLED/app environment")
        return

    if _scheduler and _scheduler.running:
        logger.warning("Scheduler already running")
        return

    _scheduler = BackgroundScheduler(timezone="UTC")

    # Fire due reminders every 5 minutes
    _scheduler.add_job(
        _execute_pending_reminders,
        trigger="interval",
        minutes=5,
        id="reminder_executor",
        replace_existing=True,
        name="Execute Pending Reminders",
    )

    # Night Brief every evening at 20:00 UTC
    _scheduler.add_job(
        _generate_night_briefs,
        trigger="cron",
        hour=20,
        minute=0,
        id="night_brief",
        replace_existing=True,
        name="Generate Night Briefs",
    )

    # Process pending joins every 30 seconds
    _scheduler.add_job(
        _process_pending_joins,
        trigger="interval",
        seconds=30,
        id="process_pending_joins",
        replace_existing=True,
        name="Staggered WhatsApp Group Joins",
    )

    _scheduler.start()
    logger.info("Background scheduler started (reminder executor + night brief + join queue jobs)")


def stop_scheduler():
    """Gracefully shut down the background scheduler"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped")
