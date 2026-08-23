"""
Integration tests for the Wave 2 wiring: prefilter, source-index attribution,
per-message anchors, and derived urgency inside process_message_batch.

These cover the seams the unit tests cannot: each module is individually tested
elsewhere, but nothing proved they were actually CALLED by the writer.
"""
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.orm import sessionmaker

from app.models import (
    AcademicEvent,
    CoverageState,
    ProcessingStatus,
    RawMessage,
    User,
    UserRole,
    WhatsAppGroup,
)
from app.services.prefilter import compute_text_hash
from app.tasks import process_message_batch


@pytest.fixture(autouse=True)
def override_tasks_db(db):
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=db.bind)
    with patch("app.database.SessionLocal", TestingSession):
        yield


@pytest.fixture
def group(db):
    user = User(
        email=f"wave2_{uuid.uuid4().hex[:6]}@example.com",
        username=f"wave2_{uuid.uuid4().hex[:6]}",
        full_name="Wave2 User",
        hashed_password="password",
        role=UserRole.STUDENT,
    )
    db.add(user)
    db.flush()
    grp = WhatsAppGroup(
        user_id=user.id,
        group_name="EEE 300L",
        group_jid=f"{uuid.uuid4().hex[:10]}@g.us",
        is_active=True,
        coverage_state=CoverageState.ACTIVE,
    )
    db.add(grp)
    db.commit()
    return grp


def _add_message(db, grp, text, created_at=None):
    row = RawMessage(
        user_id=grp.user_id,
        group_id=grp.id,
        message_id=f"m-{uuid.uuid4().hex[:10]}",
        message_text=text,
        text_hash=compute_text_hash(text),
        ai_processed=False,
        processing_status=ProcessingStatus.PENDING,
        created_at=created_at or datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    return row


def _event(**overrides):
    payload = {
        "action_type": "CREATE",
        "event_type": "DEADLINE",
        "title": "CSC301 assignment",
        "description": "Submit via portal",
        "course_code": "CSC301",
        "venue": None,
        "date_time": datetime.utcnow() + timedelta(hours=4),
        "needs_review": False,
        "confidence_score": 0.9,
    }
    payload.update(overrides)
    return payload


# -- prefilter is actually wired ----------------------------------------------

def test_prefilter_drops_fragments_before_any_llm_call(db, group):
    """A bare fragment must never reach extraction."""
    _add_message(db, group, "ok")

    with patch(
        "app.services.event_extraction_service.EventExtractionService.extract_batch_via_agnes"
    ) as mock_extract:
        result = process_message_batch(str(group.id))

    mock_extract.assert_not_called()
    assert result.startswith("prefiltered_")

    row = db.query(RawMessage).filter(RawMessage.group_id == group.id).one()
    assert row.processing_status == ProcessingStatus.SKIPPED_FRAGMENT
    assert row.ai_processed is True


def test_prefilter_does_not_skip_every_message(db, group):
    """Regression guard for the self-match bug: a real announcement must survive.

    Without exclude_message_id the repeat check matched each persisted row
    against itself and the prefilter dropped 100% of traffic.
    """
    _add_message(db, group, "CSC301 assignment is due on Friday, submit via the portal")

    with patch(
        "app.services.event_extraction_service.EventExtractionService.extract_batch_via_agnes",
        return_value=[],
    ) as mock_extract:
        result = process_message_batch(str(group.id))

    mock_extract.assert_called_once()
    assert result == "all_noise"


def test_prefilter_skips_a_true_repeat_but_keeps_the_first(db, group):
    now = datetime.utcnow()
    body = "ELE310 lecture moved to Hall B on Thursday"
    first = _add_message(db, group, body, created_at=now - timedelta(minutes=5))
    second = _add_message(db, group, body, created_at=now)

    with patch(
        "app.services.event_extraction_service.EventExtractionService.extract_batch_via_agnes",
        return_value=[],
    ) as mock_extract:
        process_message_batch(str(group.id))

    db.refresh(first)
    db.refresh(second)
    statuses = {first.processing_status, second.processing_status}
    assert ProcessingStatus.SKIPPED_REPEAT in statuses
    # Exactly one survived to extraction.
    assert mock_extract.call_count == 1
    assert len(mock_extract.call_args[0][0]) == 1


# -- source index attribution (3C) --------------------------------------------

def test_event_is_attributed_to_its_own_source_message(db, group):
    """An event carrying _source_index=2 must reference message 2, not the head."""
    m1 = _add_message(db, group, "First announcement about CSC301 coursework")
    m2 = _add_message(db, group, "Second announcement about ELE310 practical")

    events = [_event(title="ELE310 practical", course_code="ELE310", _source_index=2)]

    with patch(
        "app.services.event_extraction_service.EventExtractionService.extract_batch_via_agnes",
        return_value=events,
    ):
        with patch("app.services.notification_service.NotificationService.send_event_notification"):
            with patch("app.services.reminder_service.ReminderService.schedule_automatic_reminders"):
                process_message_batch(str(group.id))

    created = db.query(AcademicEvent).filter(AcademicEvent.group_id == group.id).one()
    assert created.source_message_id == m2.message_id
    assert created.source_message_id != m1.message_id


def test_unmappable_index_falls_back_to_batch_head_without_crashing(db, group):
    m1 = _add_message(db, group, "First announcement about CSC301 coursework")
    _add_message(db, group, "Second announcement about ELE310 practical")

    # Out of range, and a missing index, must both survive.
    events = [
        _event(title="Out of range", _source_index=99),
        _event(title="No index at all"),
    ]

    with patch(
        "app.services.event_extraction_service.EventExtractionService.extract_batch_via_agnes",
        return_value=events,
    ):
        with patch("app.services.notification_service.NotificationService.send_event_notification"):
            with patch("app.services.reminder_service.ReminderService.schedule_automatic_reminders"):
                process_message_batch(str(group.id))

    rows = db.query(AcademicEvent).filter(AcademicEvent.group_id == group.id).all()
    assert len(rows) >= 1
    assert all(r.source_message_id == m1.message_id for r in rows)


def test_source_index_never_reaches_the_orm(db, group):
    _add_message(db, group, "CSC301 assignment is due on Friday, submit via the portal")
    events = [_event(_source_index=1)]

    with patch(
        "app.services.event_extraction_service.EventExtractionService.extract_batch_via_agnes",
        return_value=events,
    ):
        with patch("app.services.notification_service.NotificationService.send_event_notification"):
            with patch("app.services.reminder_service.ReminderService.schedule_automatic_reminders"):
                process_message_batch(str(group.id))

    created = db.query(AcademicEvent).filter(AcademicEvent.group_id == group.id).one()
    assert not hasattr(created, "_source_index")


def test_two_identical_messages_in_one_batch_keep_the_first(db, group):
    """Regression guard for the mutual-exclusion bug.

    exclude_message_id alone is not enough: each row matches the OTHER copy, so
    both are marked SKIPPED_REPEAT and the announcement is lost. The call site
    must also pass `before`, making the repeat rule "keep the first, skip later
    copies".
    """
    now = datetime.utcnow()
    body = "PHY201 test has been moved to Friday in Hall C"
    first = _add_message(db, group, body, created_at=now - timedelta(seconds=30))
    second = _add_message(db, group, body, created_at=now)

    with patch(
        "app.services.event_extraction_service.EventExtractionService.extract_batch_via_agnes",
        return_value=[],
    ) as mock_extract:
        process_message_batch(str(group.id))

    db.refresh(first)
    db.refresh(second)
    assert first.processing_status != ProcessingStatus.SKIPPED_REPEAT
    assert second.processing_status == ProcessingStatus.SKIPPED_REPEAT
    mock_extract.assert_called_once()
    survivors = mock_extract.call_args[0][0]
    assert [m["id"] for m in survivors] == [str(first.id)]


# -- derived urgency (step 6) -------------------------------------------------

def test_urgency_is_derived_not_taken_from_the_payload(db, group):
    """The writer must ignore any urgency the model supplies."""
    _add_message(db, group, "CSC301 assignment is due on Friday, submit via the portal")

    # A deliberately absurd value that must NOT survive.
    events = [_event(urgency_score=0.01, _source_index=1)]

    with patch(
        "app.services.event_extraction_service.EventExtractionService.extract_batch_via_agnes",
        return_value=events,
    ):
        with patch("app.services.notification_service.NotificationService.send_event_notification"):
            with patch("app.services.reminder_service.ReminderService.schedule_automatic_reminders"):
                process_message_batch(str(group.id))

    created = db.query(AcademicEvent).filter(AcademicEvent.group_id == group.id).one()
    # 4 hours out on a DEADLINE scores high; the payload's 0.01 is discarded.
    assert created.urgency_score > 0.8


def test_imminent_deadline_outranks_distant_one_after_write(db, group):
    _add_message(db, group, "CSC301 assignment is due on Friday, submit via the portal")

    events = [
        _event(title="Due soon", course_code="AAA111",
               date_time=datetime.utcnow() + timedelta(hours=3), _source_index=1),
        _event(title="Due later", course_code="BBB222",
               date_time=datetime.utcnow() + timedelta(days=25), _source_index=1),
    ]

    with patch(
        "app.services.event_extraction_service.EventExtractionService.extract_batch_via_agnes",
        return_value=events,
    ):
        with patch("app.services.notification_service.NotificationService.send_event_notification"):
            with patch("app.services.reminder_service.ReminderService.schedule_automatic_reminders"):
                process_message_batch(str(group.id))

    soon = db.query(AcademicEvent).filter(AcademicEvent.title == "Due soon").one()
    later = db.query(AcademicEvent).filter(AcademicEvent.title == "Due later").one()
    assert soon.urgency_score > later.urgency_score


def test_day_only_precision_is_scored_as_end_of_day(db, group):
    """A DAY_ONLY date must not be scored as if it were due at 00:00.

    AcademicEvent has no date_precision column until step 5, so the writer scores
    through a view that carries the resolved precision. Without it, "due Friday"
    reads as midnight Friday and outranks an event genuinely due Friday morning.
    """
    _add_message(db, group, "CSC301 assignment is due on Friday, submit via the portal")

    midnight_tomorrow = (datetime.utcnow() + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    events = [
        _event(title="Day only", course_code="AAA111",
               date_time=midnight_tomorrow, date_precision="day_only", _source_index=1),
        _event(title="Exact midnight", course_code="BBB222",
               date_time=midnight_tomorrow, date_precision="exact", _source_index=1),
    ]

    with patch(
        "app.services.event_extraction_service.EventExtractionService.extract_batch_via_agnes",
        return_value=events,
    ):
        with patch("app.services.notification_service.NotificationService.send_event_notification"):
            with patch("app.services.reminder_service.ReminderService.schedule_automatic_reminders"):
                process_message_batch(str(group.id))

    day_only = db.query(AcademicEvent).filter(AcademicEvent.title == "Day only").one()
    exact = db.query(AcademicEvent).filter(AcademicEvent.title == "Exact midnight").one()
    # Same stored date_time, but DAY_ONLY is treated as 23:59 so it is less
    # imminent than a date the message actually pinned to midnight.
    assert day_only.urgency_score < exact.urgency_score


# -- urgency refresh is on the 5-minute cycle ---------------------------------

def test_reminder_cycle_refreshes_stale_urgency(db, group):
    """recompute_for_user must be reached by the real scheduled job.

    Urgency decays with time-to-deadline, so a score is only correct at the
    moment it is written. This proves the 5-minute cycle actually rescores.
    """
    from app.scheduler import run_reminder_cycle

    event = AcademicEvent(
        user_id=group.user_id,
        group_id=group.id,
        event_type="DEADLINE",
        course_code="CSC301",
        title="Stale score",
        date_time=datetime.utcnow() + timedelta(hours=2),
        urgency_score=0.01,  # deliberately wrong
        confidence_score=0.9,
    )
    db.add(event)
    db.commit()

    with patch("app.services.reminder_service.ReminderService.get_pending_reminders", return_value=[]):
        run_reminder_cycle()

    db.refresh(event)
    assert event.urgency_score > 0.8


def test_reminder_cycle_still_fires_reminders_when_urgency_refresh_fails(db, group):
    """A scoring failure must never block reminder delivery."""
    from app.scheduler import run_reminder_cycle

    # A live event is required, otherwise the sweep returns before it ever calls
    # recompute_for_user and the test proves nothing.
    db.add(AcademicEvent(
        user_id=group.user_id,
        group_id=group.id,
        event_type="DEADLINE",
        course_code="CSC301",
        title="Any live event",
        date_time=datetime.utcnow() + timedelta(hours=6),
        confidence_score=0.9,
    ))
    db.commit()

    with patch(
        "app.services.urgency_service.recompute_for_user",
        side_effect=RuntimeError("boom"),
    ) as mock_recompute:
        with patch(
            "app.services.reminder_service.ReminderService.get_pending_reminders",
            return_value=[],
        ) as mock_pending:
            run_reminder_cycle()

    mock_recompute.assert_called()
    mock_pending.assert_called_once()


# -- Wave 2.5: source_raw_message_id, event_index, duplicate constraint -------

def test_writer_populates_source_raw_message_id_and_event_index(db, group):
    """The writer must populate source_raw_message_id and index events per source message (0, 1...)."""
    m1 = _add_message(db, group, "CSC301 announcement with two deliverables")

    events = [
        _event(title="CSC301 Project Part 1", date_time=datetime.utcnow() + timedelta(days=2), _source_index=1),
        _event(title="CSC301 Project Part 2", date_time=datetime.utcnow() + timedelta(days=9), _source_index=1),
    ]

    with patch(
        "app.services.event_extraction_service.EventExtractionService.extract_batch_via_agnes",
        return_value=events,
    ):
        with patch("app.services.notification_service.NotificationService.send_event_notification"):
            with patch("app.services.reminder_service.ReminderService.schedule_automatic_reminders"):
                result = process_message_batch(str(group.id))

    assert result == "processed_2_events"
    saved = db.query(AcademicEvent).filter(AcademicEvent.source_raw_message_id == m1.id).order_by(AcademicEvent.event_index.asc()).all()
    assert len(saved) == 2
    assert saved[0].event_index == 0
    assert saved[0].title == "CSC301 Project Part 1"
    assert saved[0].source_raw_message_id == m1.id
    assert saved[0].source_message_id == m1.message_id
    assert saved[1].event_index == 1
    assert saved[1].title == "CSC301 Project Part 2"
    assert saved[1].source_raw_message_id == m1.id


def test_reprocessing_same_message_creates_no_second_row(db, group):
    """Reprocessing the exact same message and event index is safely caught and creates no duplicate rows."""
    m1 = _add_message(db, group, "CSC301 Quiz tomorrow")

    events = [_event(title="CSC301 Quiz tomorrow", _source_index=1)]

    with patch(
        "app.services.event_extraction_service.EventExtractionService.extract_batch_via_agnes",
        return_value=events,
    ):
        with patch("app.services.notification_service.NotificationService.send_event_notification"):
            with patch("app.services.reminder_service.ReminderService.schedule_automatic_reminders"):
                process_message_batch(str(group.id))

    count_before = db.query(AcademicEvent).filter(AcademicEvent.source_raw_message_id == m1.id).count()
    assert count_before == 1

    # Reset ai_processed to simulate a retry / duplicate worker execution on the same row
    m1.ai_processed = False
    db.commit()

    with patch(
        "app.services.event_extraction_service.EventExtractionService.extract_batch_via_agnes",
        return_value=events,
    ):
        with patch("app.services.notification_service.NotificationService.send_event_notification"):
            with patch("app.services.reminder_service.ReminderService.schedule_automatic_reminders"):
                process_message_batch(str(group.id))

    count_after = db.query(AcademicEvent).filter(AcademicEvent.source_raw_message_id == m1.id).count()
    assert count_after == 1, "Reprocessing a message must never create a second row"


def test_collision_on_one_event_does_not_destroy_the_others(db, group):
    """The real call site is a batch of many messages, not a batch of one.

    A single-event batch cannot detect this: when the constraint fires there is
    nothing else pending to lose. Here event A (message 1) is brand new and
    event B (message 2) collides with an existing row. Handling the collision
    with a bare ``db.rollback()`` discards A too -- and both messages are still
    marked ai_processed at the end of the batch, so A is never retried and the
    announcement is gone. The insert must be wrapped in a SAVEPOINT instead.
    """
    from app.models import EventStatus

    m1 = _add_message(db, group, "AAA111 assignment one is due next week")
    m2 = _add_message(db, group, "BBB222 practical session has been scheduled")

    # Occupy (user, m2.id, index 0). Deliberately unrelated in content so the
    # dedup pass cannot claim it and short-circuit before the insert.
    db.add(AcademicEvent(
        user_id=group.user_id,
        group_id=group.id,
        event_type="INFO",
        course_code="ZZZ999",
        title="Totally unrelated placeholder row",
        source_raw_message_id=m2.id,
        event_index=0,
        status=EventStatus.ACTIVE,
        confidence_score=0.9,
    ))
    db.commit()

    events = [
        _event(title="AAA111 assignment one", course_code="AAA111", _source_index=1),
        _event(title="BBB222 practical", course_code="BBB222", _source_index=2),
    ]

    with patch(
        "app.services.event_extraction_service.EventExtractionService.extract_batch_via_agnes",
        return_value=events,
    ):
        with patch("app.services.notification_service.NotificationService.send_event_notification"):
            with patch("app.services.reminder_service.ReminderService.schedule_automatic_reminders"):
                process_message_batch(str(group.id))

    survived = db.query(AcademicEvent).filter(
        AcademicEvent.source_raw_message_id == m1.id
    ).all()
    assert len(survived) == 1, (
        "the event from message 1 was destroyed by the collision on message 2"
    )
    assert survived[0].title == "AAA111 assignment one"

