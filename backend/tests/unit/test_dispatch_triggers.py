"""
Tests for 3A: dispatch triggers and the per-group dispatch lock.

The dispatcher decides WHICH groups are ready. Getting this wrong is expensive
in both directions: too eager and every "ok" costs an LLM call, too lazy and a
deadline arrives late.
"""
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.orm import sessionmaker

from app.models import (
    CoverageState,
    ProcessingStatus,
    RawMessage,
    User,
    UserRole,
    WhatsAppGroup,
)
from app.services.prefilter import compute_text_hash
from app.tasks import (
    _acquire_dispatch_lock,
    _release_dispatch_lock,
    dispatch_message_batches,
)


@pytest.fixture(autouse=True)
def override_tasks_db(db):
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=db.bind)
    with patch("app.database.SessionLocal", TestingSession):
        yield


@pytest.fixture
def group(db):
    user = User(
        email=f"disp_{uuid.uuid4().hex[:6]}@example.com",
        username=f"disp_{uuid.uuid4().hex[:6]}",
        full_name="Dispatch User",
        hashed_password="password",
        role=UserRole.STUDENT,
    )
    db.add(user)
    db.flush()
    grp = WhatsAppGroup(
        user_id=user.id,
        group_name="MEE 400L",
        group_jid=f"{uuid.uuid4().hex[:10]}@g.us",
        is_active=True,
        coverage_state=CoverageState.ACTIVE,
    )
    db.add(grp)
    db.commit()
    return grp


@pytest.fixture(autouse=True)
def clean_locks(group):
    _release_dispatch_lock(group.id)
    yield
    _release_dispatch_lock(group.id)


def _add(db, grp, text="Just a quick note here", created_at=None, **kw):
    fields = {
        "ai_processed": False,
        "processing_status": ProcessingStatus.PENDING,
    }
    fields.update(kw)
    row = RawMessage(
        user_id=grp.user_id,
        group_id=grp.id,
        message_id=f"m-{uuid.uuid4().hex[:10]}",
        message_text=text,
        text_hash=compute_text_hash(text),
        created_at=created_at or datetime.utcnow(),
        **fields,
    )
    db.add(row)
    db.commit()
    return row


# ── Triggers ──────────────────────────────────────────────────────────────────

def test_fresh_small_batch_is_not_dispatched(db, group):
    """Below every threshold the group must accumulate, not burn an LLM call."""
    _add(db, group, "morning everyone how are you all")

    with patch("app.tasks.process_message_batch.delay") as mock_delay:
        result = dispatch_message_batches()

    mock_delay.assert_not_called()
    assert result == "no_group_triggered"


def test_size_trigger_dispatches(db, group):
    from app.config import settings

    for _ in range(settings.batch_size_trigger):
        _add(db, group, f"chatter message number {uuid.uuid4().hex[:6]}")

    with patch("app.tasks.process_message_batch.delay") as mock_delay:
        result = dispatch_message_batches()

    mock_delay.assert_called_once_with(str(group.id))
    assert result == "dispatched_1"


def test_age_trigger_dispatches(db, group):
    """A lone message must not wait forever just because the batch is small."""
    from app.config import settings

    old = datetime.utcnow() - timedelta(
        seconds=settings.batch_age_trigger_seconds + 30
    )
    _add(db, group, "a quiet little message", created_at=old)

    with patch("app.tasks.process_message_batch.delay") as mock_delay:
        dispatch_message_batches()

    mock_delay.assert_called_once_with(str(group.id))


def test_tripwire_keyword_dispatches_immediately(db, group):
    """"cancelled" cannot wait for the age trigger."""
    _add(db, group, "Tomorrow's lecture has been cancelled")

    with patch("app.tasks.process_message_batch.delay") as mock_delay:
        dispatch_message_batches()

    mock_delay.assert_called_once_with(str(group.id))


def test_tripwire_is_case_insensitive_and_portable(db, group):
    """SQLite has no ILIKE, so the match must be built with lower() + LIKE."""
    _add(db, group, "URGENT: submission window closes")

    with patch("app.tasks.process_message_batch.delay") as mock_delay:
        dispatch_message_batches()

    mock_delay.assert_called_once_with(str(group.id))


def test_quarantined_and_exhausted_rows_never_trigger(db, group):
    from app.config import settings

    old = datetime.utcnow() - timedelta(
        seconds=settings.batch_age_trigger_seconds + 30
    )
    _add(db, group, "poison message cancelled", created_at=old,
         processing_status=ProcessingStatus.QUARANTINED)
    _add(db, group, "exhausted message cancelled", created_at=old,
         ai_attempts=settings.batch_max_attempts)

    with patch("app.tasks.process_message_batch.delay") as mock_delay:
        result = dispatch_message_batches()

    mock_delay.assert_not_called()
    assert result == "no_unprocessed_groups"


def test_inactive_group_is_not_dispatched(db, group):
    group.is_active = False
    db.commit()
    _add(db, group, "lecture cancelled tomorrow")

    with patch("app.tasks.process_message_batch.delay") as mock_delay:
        result = dispatch_message_batches()

    mock_delay.assert_not_called()
    assert result == "no_unprocessed_groups"


def test_already_processed_messages_do_not_trigger(db, group):
    _add(db, group, "lecture cancelled tomorrow", ai_processed=True)

    with patch("app.tasks.process_message_batch.delay") as mock_delay:
        result = dispatch_message_batches()

    mock_delay.assert_not_called()
    assert result == "no_unprocessed_groups"


# ── Per-group dispatch lock ───────────────────────────────────────────────────

def test_group_with_batch_in_flight_is_not_dispatched_twice(db, group):
    """At a 30s beat a still-running batch would otherwise be re-dispatched.

    ai_processed is only flipped at the END of a successful batch, so a second
    worker would load and process exactly the same rows.
    """
    _add(db, group, "lecture cancelled tomorrow")

    assert _acquire_dispatch_lock(group.id) is True
    try:
        with patch("app.tasks.process_message_batch.delay") as mock_delay:
            result = dispatch_message_batches()

        mock_delay.assert_not_called()
        assert result == "no_group_triggered"
    finally:
        _release_dispatch_lock(group.id)


def test_lock_is_released_after_the_batch_completes(db, group):
    """Otherwise one dispatch would wedge the group for the staleness window."""
    from app.tasks import process_message_batch

    _add(db, group, "lecture cancelled tomorrow")
    assert _acquire_dispatch_lock(group.id) is True

    with patch(
        "app.services.event_extraction_service.EventExtractionService.extract_batch_via_agnes",
        return_value=[],
    ):
        process_message_batch(str(group.id))

    # Free again, so the next cycle can dispatch.
    assert _acquire_dispatch_lock(group.id) is True
    _release_dispatch_lock(group.id)


def test_lock_is_released_even_when_the_batch_raises(db, group):
    from app.tasks import process_message_batch

    _add(db, group, "lecture cancelled tomorrow")
    assert _acquire_dispatch_lock(group.id) is True

    with patch(
        "app.services.event_extraction_service.EventExtractionService.extract_batch_via_agnes",
        side_effect=RuntimeError("boom"),
    ):
        with pytest.raises(RuntimeError):
            process_message_batch(str(group.id))

    assert _acquire_dispatch_lock(group.id) is True
    _release_dispatch_lock(group.id)


def test_bisect_children_are_exempt_from_the_lock(db, group):
    """3B enqueues TWO jobs for one group; a per-group lock would deadlock them.

    The explicit message_ids path must neither acquire nor release the lock.
    """
    from app.tasks import process_message_batch

    m1 = _add(db, group, "first announcement about cancelled lecture")
    m2 = _add(db, group, "second announcement about cancelled lab")

    # Simulate the dispatcher holding the lock for the parent run.
    assert _acquire_dispatch_lock(group.id) is True
    try:
        with patch(
            "app.services.event_extraction_service.EventExtractionService.extract_batch_via_agnes",
            return_value=[],
        ) as mock_extract:
            process_message_batch(str(group.id), [str(m1.id)])
            process_message_batch(str(group.id), [str(m2.id)])

        # Both children ran despite the group being locked.
        assert mock_extract.call_count == 2
        # And neither released the parent's lock.
        assert _acquire_dispatch_lock(group.id) is False
    finally:
        _release_dispatch_lock(group.id)


def test_stale_lock_is_taken_over(db, group):
    """A worker killed mid-batch must not wedge its group permanently."""
    import os
    import tempfile

    from app.tasks import _dispatch_lock_key

    assert _acquire_dispatch_lock(group.id) is True
    path = os.path.join(tempfile.gettempdir(), _dispatch_lock_key(group.id))
    # Backdate well beyond the staleness window.
    old = datetime.utcnow().timestamp() - 10_000
    os.utime(path, (old, old))

    assert _acquire_dispatch_lock(group.id) is True
    _release_dispatch_lock(group.id)
