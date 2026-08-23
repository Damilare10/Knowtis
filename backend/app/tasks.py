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
from types import SimpleNamespace

from celery import Task

from app.celery_app import celery_app
from app.config import settings

logger = logging.getLogger(__name__)


GROUP_BROADCAST_TAGS = {
    "@all",
    "@everyone",
    "@here",
}


def _is_tagged_bot_command(data: dict) -> bool:
    """
    A message is ONLY a bot command if the bot was explicitly tagged or mentioned.
    Never use text content or sentence structure to infer a bot command in group chats.
    """
    message_text = data.get("message_text") or data.get("text") or ""
    text_lower = message_text.lower()

    # 1. Exclude mass broadcast tags (@everyone/@all/@here) unless directly tagged
    if data.get("mention_all") or any(tag in text_lower for tag in GROUP_BROADCAST_TAGS):
        return False

    # 2. Direct mention of the bot (calculated by connector: JID in mentioned_jids or @botPhone)
    if data.get("is_bot_mentioned"):
        return True

    # 3. Explicit text mention of '@knowtis' or '@bot'
    if re.search(r"@knowtis\b|@bot\b", text_lower):
        return True

    return False


def _strip_calendar_command_text(message_text: str) -> str:
    clean_msg = message_text or ""
    clean_msg = re.sub(r"@\S+", "", clean_msg)
    clean_msg = re.sub(rf"(?i)knowtis", "", clean_msg)
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
    Persist-only webhook handler.

    Saves the inbound WhatsApp message to ``RawMessage`` with
    ``ai_processed = False``.  The batch writer
    (``process_message_batch``) picks it up on its next 2-minute cycle.

    The tagged-bot-command branch (LangGraph) is kept intact — it is an
    unrelated feature that does not write event rows.
    """
    from app.database import SessionLocal
    from app.models import (
        WhatsAppGroup, RawMessage,
        ProcessingStatus,
    )
    from app.services.notification_service import NotificationService

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
        # Detect direct bot-tagged command
        if _is_tagged_bot_command(data):
            from app.models import User

            sender_phone = (
                "".join(c for c in sender_jid.split("@")[0] if c.isdigit())
                if sender_jid
                else None
            )
            sync_user = db.query(User).filter(User.whatsapp_number == sender_phone).first() if sender_phone else None
            user_id = str(sync_user.id) if sync_user else None

            # Clean tag from prompt text
            clean_prompt = _strip_calendar_command_text(message_text)
            prompt_to_agent = clean_prompt if clean_prompt else message_text

            logger.info(f"Routing bot tag command directly to LangGraph Multi-Agent Engine: '{prompt_to_agent}' (user={user_id})")

            try:
                try:
                    from langgraph_agent import run_knowtis_agent
                except ImportError:
                    from app.services.langgraph_agent import run_knowtis_agent

                agent_result = run_knowtis_agent(
                    query=prompt_to_agent,
                    user_id=user_id,
                    thread_id=f"wa_tag_{group_jid}_{sender_phone or 'anon'}"
                )
                answer = agent_result.get("answer", "")

                # If user is registered, dispatch immediate push alert feedback
                if sync_user and answer:
                    NotificationService.dispatch_alert(
                        user_id=sync_user.id,
                        title="Knowtis AI Response",
                        description=answer[:250] + ("..." if len(answer) > 250 else ""),
                        db=db,
                        alert_level="info",
                        push=True,
                    )
                return "bot_command_processed_via_langgraph"
            except Exception as e:
                logger.error(f"Failed to process tagged bot command via LangGraph agent: {e}")

        # Find all active groups monitoring this JID
        active_groups = db.query(WhatsAppGroup).filter(
            WhatsAppGroup.group_jid == group_jid,
            WhatsAppGroup.is_active == True
        ).all()

        if not active_groups:
            logger.info(f"Asynchronously ignored message in group {group_jid}: group is not monitored by any user.")
            return "ignored_group_not_monitored"

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

            # Persist to RawMessage audit log (ai_processed defaults to False)
            raw = RawMessage(
                user_id=group.user_id,
                group_id=group.id,
                message_id=message_id,
                sender_jid=sender_jid,
                sender_name=sender_name,
                message_text=message_text,
                message_type="text",
                quoted_message_id=data.get("quoted_message_id"),
                quoted_message_text=data.get("quoted_message_text"),
                processing_status=ProcessingStatus.PROCESSED,
                created_at=datetime.utcnow()
            )
            db.add(raw)
            db.commit()

            # Update coverage timestamp
            group.last_coverage_update = datetime.utcnow()
            db.commit()

        logger.info(f"Persisted webhook message for {len(active_groups)} group(s). Batch writer will extract events.")
        return f"persisted_{len(active_groups)}_groups"

    except Exception as e:
        logger.exception("Error in process_incoming_message_task")
        db.rollback()
        raise
    finally:
        db.close()



@celery_app.task(name="app.tasks.send_pending_reminders_task", base=RateLimitedTask)
def send_pending_reminders_task():
    """Asynchronous task wrapper for the 5-minute cycle.

    Runs the same ``run_reminder_cycle`` as the in-process scheduler, so derived
    urgency is refreshed on this cadence whichever driver is active.
    """
    from app.scheduler import run_reminder_cycle
    run_reminder_cycle()
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


def _tripwire_clause(column, keywords):
    """Portable case-insensitive keyword match.

    SQLite has no ``ILIKE``, and SQLAlchemy's ``ilike`` compiles to
    ``lower(x) LIKE lower(y)`` there, which is fine, but the pattern still has to
    be built per keyword. Kept as one helper so the dispatcher and its tests
    cannot drift apart.
    """
    from sqlalchemy import func, or_

    clauses = [
        func.lower(column).like(f"%{kw}%")
        for kw in (k.strip().lower() for k in keywords)
        if kw
    ]
    return or_(*clauses) if clauses else None


def _dispatch_lock_key(group_id) -> str:
    # Normalised so a UUID object and its string form map to the same lock: the
    # dispatcher holds a UUID, the task receives a string.
    return f"knowtis_dispatch_{str(group_id).lower()}"


def _acquire_dispatch_lock(group_id) -> bool:
    """Take a short-lived per-group dispatch lock. True when acquired.

    At a 30-second beat a batch that is still running would otherwise be
    dispatched again, and two workers would load and process the same rows:
    ``ai_processed`` is only flipped at the END of a successful batch, so the
    second worker sees the same unprocessed set.

    Uses the same atomic ``O_CREAT | O_EXCL`` file pattern as
    ``scheduler._acquire_scheduler_lock``, including its staleness rule, so a
    worker that is killed mid-batch cannot wedge a group permanently.

    NOTE: this is per-host. It stops the duplicate-dispatch case that the 30s
    beat creates on a single worker host, not distributed contention across
    hosts; a multi-host deployment needs the Redis lock noted in the TODO.
    """
    import os
    import tempfile

    from app.config import settings

    path = os.path.join(tempfile.gettempdir(), _dispatch_lock_key(group_id))
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        try:
            age = time.time() - os.path.getmtime(path)
            if age < settings.batch_dispatch_lock_seconds:
                return False
            # Stale: the previous holder died mid-batch. Take it over.
            os.remove(path)
            return _acquire_dispatch_lock(group_id)
        except OSError:
            return False
    except OSError:
        return False


def _release_dispatch_lock(group_id) -> None:
    import os
    import tempfile

    try:
        os.remove(os.path.join(tempfile.gettempdir(), _dispatch_lock_key(group_id)))
    except OSError:
        pass


@celery_app.task(name="app.tasks.dispatch_message_batches", base=RateLimitedTask)
def dispatch_message_batches():
    """Fan-out dispatcher: decide WHICH groups are ready, then enqueue one batch each.

    Runs every 30 seconds via Celery beat. The cadence has to be tighter than the
    age trigger it enforces: at the old 2-minute beat an "older than 90s" rule
    could never fire on time, because the first evaluation after a message
    arrived was already up to 120s late.

    A group is dispatched when ANY of (§6.1):
      * it has accumulated ``batch_size_trigger`` unprocessed messages,
      * its oldest unprocessed message is older than ``batch_age_trigger_seconds``,
      * any unprocessed message contains a tripwire keyword.

    Groups below every threshold are left to accumulate, which is the point:
    batching several messages into one LLM call is what makes the pipeline
    affordable, and a lone "ok" should not trigger a call at all.
    """
    from datetime import timedelta

    from sqlalchemy import func

    from app.config import settings
    from app.database import SessionLocal
    from app.models import CoverageState, ProcessingStatus, RawMessage, WhatsAppGroup

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        age_cutoff = now - timedelta(seconds=settings.batch_age_trigger_seconds)
        keywords = settings.batch_tripwire_keywords.split(",")

        eligible = (
            RawMessage.ai_processed == False,  # noqa: E712
            RawMessage.message_text.isnot(None),
            RawMessage.message_text != "",
            RawMessage.ai_attempts < settings.batch_max_attempts,
            RawMessage.processing_status != ProcessingStatus.QUARANTINED,
        )

        # One aggregate pass instead of a query per group: count the backlog and
        # find the oldest message per group in a single round trip.
        rows = (
            db.query(
                RawMessage.group_id,
                func.count(RawMessage.id).label("pending"),
                func.min(RawMessage.created_at).label("oldest"),
            )
            .join(WhatsAppGroup, WhatsAppGroup.id == RawMessage.group_id)
            .filter(
                *eligible,
                WhatsAppGroup.is_active == True,  # noqa: E712
                WhatsAppGroup.coverage_state == CoverageState.ACTIVE,
            )
            .group_by(RawMessage.group_id)
            .all()
        )

        if not rows:
            return "no_unprocessed_groups"

        # Tripwire groups, resolved once for the whole cycle.
        tripwire_groups = set()
        clause = _tripwire_clause(RawMessage.message_text, keywords)
        if clause is not None:
            candidate_ids = [r.group_id for r in rows]
            tripwire_groups = {
                gid
                for (gid,) in db.query(RawMessage.group_id)
                .filter(*eligible, RawMessage.group_id.in_(candidate_ids), clause)
                .distinct()
                .all()
            }

        dispatched = 0
        skipped_waiting = 0
        skipped_locked = 0
        for row in rows:
            reasons = []
            if row.pending >= settings.batch_size_trigger:
                reasons.append(f"size={row.pending}")
            if row.oldest is not None and row.oldest <= age_cutoff:
                reasons.append(f"age={(now - row.oldest).total_seconds():.0f}s")
            if row.group_id in tripwire_groups:
                reasons.append("tripwire")

            if not reasons:
                skipped_waiting += 1
                continue

            # TODO(step-3): replace the file lock with a Redis SET NX EX lock so
            # this holds across worker hosts, not just per host.
            if not _acquire_dispatch_lock(row.group_id):
                skipped_locked += 1
                logger.debug(
                    "Group %s already has a batch in flight; not dispatching",
                    row.group_id,
                )
                continue

            # The lock is released by process_message_batch, not here. If the
            # enqueue itself fails the group would stay locked until the
            # staleness window, so release it on that path explicitly.
            try:
                process_message_batch.delay(str(row.group_id))
            except Exception:
                _release_dispatch_lock(row.group_id)
                raise
            dispatched += 1
            logger.info(
                "Dispatched batch for group %s (%s)", row.group_id, ", ".join(reasons)
            )

        if skipped_waiting or skipped_locked:
            logger.debug(
                "Dispatch cycle: %d dispatched, %d below threshold, %d locked",
                dispatched, skipped_waiting, skipped_locked,
            )

        if not dispatched:
            return "no_group_triggered"
        return f"dispatched_{dispatched}"

    except Exception:
        logger.exception("Error in dispatch_message_batches")
        raise
    finally:
        db.close()


@celery_app.task(name="app.tasks.process_message_batch", base=RateLimitedTask)
def process_message_batch(group_id: str, message_ids: list[str] | None = None):
    """THE ONLY WRITER to ``academic_events``.

    Fetches unprocessed ``RawMessage`` rows for a single group (either a specific
    subset given by ``message_ids`` or up to 15 oldest eligible), sends them to
    Agnes batch extraction, and reconciles each extracted event through
    ``DeduplicationService.reconcile_event``.

    ``ai_processed`` is set to ``True`` and ``ai_attempts`` is reset to 0 only after
    the batch succeeds. Failures increment ``ai_attempts``, triggering bisect or
    quarantine.

    Locking: the DISPATCHER takes the per-group lock before enqueuing, and this
    task releases it when the auto-select run finishes. The explicit
    ``message_ids`` path never takes or releases it, because 3B enqueues two
    bisect children for the same group and a per-group lock would deadlock them
    against each other.
    """
    import uuid as _uuid
    from sqlalchemy.exc import IntegrityError
    from app.config import settings
    from app.database import SessionLocal
    from app.models import (
        WhatsAppGroup, RawMessage, AcademicEvent, EventType, ProcessingStatus,
        EventStatus, EventDatePrecision
    )
    from app.services.event_extraction_service import EventExtractionService
    from app.services.deduplication_service import DeduplicationService
    from app.services.notification_service import NotificationService
    from app.services.reminder_service import ReminderService
    from app.services.urgency_service import compute_urgency
    from app.utils import generate_embedding

    holds_dispatch_lock = message_ids is None

    db = SessionLocal()
    try:
        parsed_gid = _uuid.UUID(str(group_id)) if not isinstance(group_id, _uuid.UUID) else group_id
        group = db.query(WhatsAppGroup).filter(WhatsAppGroup.id == parsed_gid).first()
        if not group or not group.is_active:
            logger.info("process_message_batch: group %s missing or inactive, skipping", group_id)
            return "skipped_inactive"

        if message_ids is not None:
            parsed_ids = [_uuid.UUID(str(m)) if not isinstance(m, _uuid.UUID) else m for m in message_ids]
            # NOTE: deliberately NOT filtered on ai_attempts. The caller is the
            # bisect path, which has already decided these rows must be
            # processed. Applying the ceiling here stopped bisect children from
            # loading once attempts hit the max, so any batch larger than
            # 2 ** (batch_max_attempts - batch_bisect_after) stalled at
            # attempts == max with status PENDING: never processed, never
            # quarantined, invisible to operators. Auto-selection below still
            # honours the ceiling, and so does dispatch_message_batches, so
            # exhausted rows are never picked up fresh.
            unprocessed = (
                db.query(RawMessage)
                .filter(
                    RawMessage.group_id == group.id,
                    RawMessage.id.in_(parsed_ids),
                    RawMessage.ai_processed == False,
                    RawMessage.message_text.isnot(None),
                    RawMessage.message_text != "",
                    RawMessage.processing_status != ProcessingStatus.QUARANTINED,
                )
                .order_by(RawMessage.created_at.asc())
                .all()
            )
        else:
            # §3.1 step 2: limit 15 per review §6.2
            unprocessed = (
                db.query(RawMessage)
                .filter(
                    RawMessage.group_id == group.id,
                    RawMessage.ai_processed == False,
                    RawMessage.message_text.isnot(None),
                    RawMessage.message_text != "",
                    RawMessage.ai_attempts < settings.batch_max_attempts,
                    RawMessage.processing_status != ProcessingStatus.QUARANTINED,
                )
                .order_by(RawMessage.created_at.asc())
                .limit(15)
                .all()
            )

        if not unprocessed:
            return "no_unprocessed"

        # Deterministic prefilter: drop empty / fragment / repeat messages before
        # they cost an LLM call. exclude_message_id is REQUIRED here: these rows
        # are already persisted with their text_hash, so without it every message
        # matches itself and the prefilter skips all traffic.
        from app.services.prefilter import classify_skip

        survivors = []
        skipped = 0
        for msg in unprocessed:
            # `before` is REQUIRED alongside exclude_message_id. The repeat rule
            # is "keep the first, skip later copies", which needs an ordering:
            # with only the id exclusion, two identical messages in the same
            # batch each match the OTHER one and both are skipped, losing the
            # announcement outright.
            skip_status = classify_skip(
                msg.message_text,
                group.id,
                db,
                exclude_message_id=msg.id,
                before=msg.created_at,
            )
            if skip_status is not None:
                msg.processing_status = skip_status
                msg.ai_processed = True
                msg.ai_attempts = 0
                skipped += 1
            else:
                survivors.append(msg)

        if skipped:
            db.commit()
            logger.info(
                "Prefilter skipped %d/%d message(s) for group %s before any LLM call",
                skipped, len(unprocessed), group.group_name,
            )

        if not survivors:
            return f"prefiltered_{skipped}"

        unprocessed = survivors

        # Build payload. created_at travels with each message so every extracted
        # event resolves its date against its OWN source message rather than the
        # batch head; a 15-message batch can cross midnight.
        messages_payload = [
            {
                "id": str(msg.id),
                "message_text": msg.message_text,
                "created_at": msg.created_at,
            }
            for msg in unprocessed
        ]

        # Fallback anchor only, for events whose index cannot be mapped.
        anchor = unprocessed[0].created_at

        # Call Agnes batch extraction
        events = EventExtractionService.extract_batch_via_agnes(
            messages_payload, msg_created_at=anchor, db=db
        )

        if events is None:
            # Extraction FAILED (network error, timeout, rate limit, or invalid JSON).
            all_ids = [u.id for u in unprocessed]
            db.query(RawMessage).filter(RawMessage.id.in_(all_ids)).update(
                {"ai_attempts": RawMessage.ai_attempts + 1}, synchronize_session=False
            )
            db.commit()

            # db.commit() expires instances in session; accessing m.ai_attempts reads the newly updated value
            attempts = max((m.ai_attempts for m in unprocessed), default=1)

            if attempts >= settings.batch_bisect_after and len(unprocessed) > 1:
                mid = len(unprocessed) // 2
                left = [str(m.id) for m in unprocessed[:mid]]
                right = [str(m.id) for m in unprocessed[mid:]]
                process_message_batch.delay(group_id, left)
                process_message_batch.delay(group_id, right)
                logger.warning(
                    "Agnes batch extraction failed for group %s (attempt %d >= %d). "
                    "Bisecting %d messages into subsets [%d, %d]",
                    group_id, attempts, settings.batch_bisect_after,
                    len(unprocessed), len(left), len(right)
                )
                return f"bisected_{len(left)}_{len(right)}"

            if len(unprocessed) == 1 and attempts >= settings.batch_max_attempts:
                unprocessed[0].processing_status = ProcessingStatus.QUARANTINED
                db.commit()
                logger.error(
                    "Quarantined poison message %s after %d attempts",
                    unprocessed[0].id, attempts
                )
                return "quarantined"

            logger.error(
                "Agnes batch extraction failed for group %s (%s): leaving %d "
                "message(s) unprocessed for retry (attempts=%d)",
                group.group_name,
                group.id,
                len(unprocessed),
                attempts,
            )
            return "extraction_failed"

        if not events:
            # Successful parse that yielded no academic events -> genuinely all
            # noise. Safe to mark processed and reset attempts.
            all_ids = [u.id for u in unprocessed]
            db.query(RawMessage).filter(RawMessage.id.in_(all_ids)).update(
                {
                    "ai_processed": True,
                    "processing_status": ProcessingStatus.PROCESSED,
                    "ai_attempts": 0,
                },
                synchronize_session=False,
            )
            db.commit()
            logger.info(
                "Batch for group %s classified all %d message(s) as noise",
                group.group_name,
                len(unprocessed),
            )
            return "all_noise"

        processed_total = 0
        raw_event_counts = {}

        # Map the 1-based index Agnes returns back to the source message, and
        # validate hard: a dropped or renumbered index would otherwise silently
        # attribute an event to the wrong message.
        index_to_raw = {i + 1: m for i, m in enumerate(unprocessed)}
        seen_indices = [e.get("_source_index") for e in events if e.get("_source_index")]
        if len(seen_indices) != len(set(seen_indices)):
            logger.warning(
                "Agnes returned duplicate source indices for group %s: %s",
                group.id, seen_indices,
            )
        missing_index = sum(1 for e in events if e.get("_source_index") is None)
        if missing_index:
            logger.warning(
                "Agnes omitted the index on %d/%d event(s) for group %s",
                missing_index, len(events), group.id,
            )

        for event_data in events:
            if not event_data or not event_data.get("title"):
                continue

            # Resolve the source message before reconciling, and strip the
            # internal plumbing key so it can never reach the ORM.
            src_index = event_data.pop("_source_index", None)
            src_raw = index_to_raw.get(src_index) if isinstance(src_index, int) else None
            if src_raw is None:
                logger.warning(
                    "Unmappable source index %r for group %s; attributing to batch head",
                    src_index, group.id,
                )
                src_raw = unprocessed[0]

            event_idx = raw_event_counts.get(src_raw.id, 0)
            raw_event_counts[src_raw.id] = event_idx + 1

            # Route through reconcile_event — never a bare db.add()
            reconciled_event, outcome = DeduplicationService.reconcile_event(
                user_id=group.user_id,
                event_data=event_data,
                group_id=group.id,
                db=db,
            )

            if outcome == "DUPLICATE":
                continue

            if outcome in ("UPDATED", "CANCELLED") and reconciled_event:
                # Urgency depends on date_time, which an UPDATE may have moved.
                if event_data.get("date_precision") and event_data.get("date_time"):
                    reconciled_event.date_precision = event_data["date_precision"]
                reconciled_event.urgency_score = compute_urgency(reconciled_event)
                
                # Notify on mutation
                if not reconciled_event.needs_review:
                    NotificationService.dispatch_alert(
                        user_id=group.user_id,
                        title=f"{'Cancelled' if outcome == 'CANCELLED' else 'Updated'}: {reconciled_event.title[:200]}",
                        description=reconciled_event.description[:1000] if reconciled_event.description else "",
                        db=db,
                        event_id=reconciled_event.id,
                        alert_level="urgent" if outcome == "CANCELLED" else "info",
                        push=True,
                    )
                processed_total += 1
                continue

            # CREATE: Brand new event — use canonical dedup text for embedding (§3.7)
            canonical_text = EventExtractionService.canonical_dedup_text(event_data)
            embedding = generate_embedding(canonical_text)

            academic_event = AcademicEvent(
                user_id=group.user_id,
                group_id=group.id,
                event_type=event_data["event_type"],
                course_code=event_data.get("course_code"),
                title=event_data["title"][:500],
                description=event_data.get("description"),
                venue=event_data.get("venue"),
                date_time=event_data.get("date_time"),
                confidence_score=event_data.get("confidence_score", 0.8),
                relevance_score=event_data.get("relevance_score", 0.7),
                actionability_score=event_data.get("actionability_score", 0.6),
                needs_review=bool(event_data.get("needs_review", True)),
                embedding=json.dumps(embedding) if embedding else None,
                source_message_id=src_raw.message_id,
                source_raw_message_id=src_raw.id,
                event_index=event_idx,
                date_precision=event_data.get("date_precision") or EventDatePrecision.UNKNOWN,
                status=EventStatus.ACTIVE,
                source_group_jid=group.group_jid,
            )
            academic_event.urgency_score = compute_urgency(academic_event)
            try:
                # SAVEPOINT, not a bare db.rollback(). A collision on THIS event
                # must not discard events already flushed earlier in the same
                # batch: every message in the batch is marked ai_processed at the
                # end regardless, so anything lost here is lost permanently and
                # is never retried.
                with db.begin_nested():
                    db.add(academic_event)
                    db.flush()
            except IntegrityError as exc:
                logger.warning(
                    "Duplicate event constraint caught on create (user=%s, raw_message=%s, index=%d): %s",
                    group.user_id, src_raw.id, event_idx, exc,
                )
                continue

            # Gate notifications/reminders on needs_review
            if not academic_event.needs_review:
                if academic_event.event_type == EventType.ALERT:
                    NotificationService.dispatch_alert(
                        user_id=group.user_id,
                        title=f"Alert: {academic_event.title}",
                        description=academic_event.description or academic_event.title,
                        db=db,
                        event_id=academic_event.id,
                        alert_level="urgent",
                        push=True,
                    )
                else:
                    ReminderService.schedule_automatic_reminders(academic_event, db)
                    NotificationService.send_event_notification(
                        group.user, academic_event, "IN_APP", db
                    )

            processed_total += 1

        # Mark ai_processed = True only after the loop completes without raising
        all_ids = [u.id for u in unprocessed]
        db.query(RawMessage).filter(RawMessage.id.in_(all_ids)).update(
            {
                "ai_processed": True,
                "processing_status": ProcessingStatus.PROCESSED,
                "ai_attempts": 0,
            },
            synchronize_session=False,
        )
        db.commit()

        logger.info(
            "Batch complete for group %s: %d event(s) extracted from %d message(s)",
            group.group_name, processed_total, len(unprocessed),
        )
        return f"processed_{processed_total}_events"

    except Exception:
        logger.exception("Error in process_message_batch for group %s", group_id)
        db.rollback()
        raise
    finally:
        db.close()
        # Release even on failure: holding the lock after a crash would stall the
        # group until the staleness window expired.
        if holds_dispatch_lock:
            _release_dispatch_lock(group_id)
