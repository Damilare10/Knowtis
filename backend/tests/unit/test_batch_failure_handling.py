"""
Unit tests for WhatsApp pipeline Step 3B: batch failure handling, bisect, and quarantine.
"""
import uuid
from unittest.mock import patch, MagicMock
import pytest
from sqlalchemy.orm import sessionmaker
from app.models import WhatsAppGroup, RawMessage, CoverageState, ProcessingStatus, AcademicEvent, User, UserRole
from app.config import settings
from app.tasks import process_message_batch, dispatch_message_batches


@pytest.fixture(autouse=True)
def override_tasks_db(db):
    """Ensure background tasks use the test database engine/sessionmaker."""
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=db.bind)
    with patch("app.database.SessionLocal", TestingSession):
        yield


@pytest.fixture
def group_and_messages(db):
    """Fixture providing a user, active group, and 4 raw messages."""
    user = User(
        email="test_batch@example.com",
        username="test_batch_user",
        full_name="Batch Test User",
        hashed_password="password",
        role=UserRole.STUDENT,
    )
    db.add(user)
    db.flush()

    group = WhatsAppGroup(
        user_id=user.id,
        group_name="Test CS Level 300",
        group_jid="123456789@g.us",
        is_active=True,
        coverage_state=CoverageState.ACTIVE,
    )
    db.add(group)
    db.flush()

    messages = []
    for i in range(4):
        msg = RawMessage(
            user_id=user.id,
            group_id=group.id,
            message_id=f"msg_{i+1}",
            sender_jid="sender@s.whatsapp.net",
            message_text=f"Test message {i+1}",
            ai_processed=False,
            processing_status=ProcessingStatus.PENDING,
            ai_attempts=0,
        )
        db.add(msg)
        messages.append(msg)
    db.commit()

    return user, group, messages


def test_batch_failure_increments_attempts_and_bisects(db, group_and_messages):
    """
    When extraction fails repeatedly, attempts are incremented.
    When attempts reach batch_bisect_after (default 3) and batch > 1,
    the batch is bisected and two sub-tasks are enqueued.
    """
    user, group, messages = group_and_messages

    # Patch extract_batch_via_agnes to simulate extraction failure (returns None)
    with patch("app.services.event_extraction_service.EventExtractionService.extract_batch_via_agnes", return_value=None):
        with patch.object(process_message_batch, "delay") as mock_delay:
            # 1st attempt: attempts -> 1 (no bisect yet)
            res1 = process_message_batch(str(group.id))
            assert res1 == "extraction_failed"
            assert mock_delay.call_count == 0

            for msg in messages:
                db.refresh(msg)
                assert msg.ai_attempts == 1
                assert msg.ai_processed is False

            # 2nd attempt: attempts -> 2 (no bisect yet)
            res2 = process_message_batch(str(group.id))
            assert res2 == "extraction_failed"
            assert mock_delay.call_count == 0

            for msg in messages:
                db.refresh(msg)
                assert msg.ai_attempts == 2

            # 3rd attempt: attempts -> 3 (batch_bisect_after = 3, len = 4)
            res3 = process_message_batch(str(group.id))
            assert res3.startswith("bisected_")
            assert mock_delay.call_count == 2

            # Verify the two bisected calls were made with subsets
            call_args_list = mock_delay.call_args_list
            left_call = call_args_list[0][0]
            right_call = call_args_list[1][0]
            assert left_call[0] == str(group.id)
            assert len(left_call[1]) == 2
            assert right_call[0] == str(group.id)
            assert len(right_call[1]) == 2


def test_poison_message_quarantined_after_max_attempts(db, group_and_messages):
    """
    A single poison message (len == 1) failing up to batch_max_attempts
    is marked QUARANTINED and stopped from future selection.
    """
    user, group, messages = group_and_messages
    poison_msg = messages[0]

    # Delete other messages so only 1 message remains in group
    for msg in messages[1:]:
        db.delete(msg)
    db.commit()

    with patch("app.services.event_extraction_service.EventExtractionService.extract_batch_via_agnes", return_value=None):
        # Fail 4 times (attempts 1 to 4)
        for i in range(4):
            res = process_message_batch(str(group.id), message_ids=[str(poison_msg.id)])
            assert res == "extraction_failed"
            db.refresh(poison_msg)
            assert poison_msg.ai_attempts == i + 1
            assert poison_msg.processing_status != ProcessingStatus.QUARANTINED

        # 5th failure (batch_max_attempts = 5): message is quarantined
        res5 = process_message_batch(str(group.id), message_ids=[str(poison_msg.id)])
        assert res5 == "quarantined"
        db.refresh(poison_msg)
        assert poison_msg.ai_attempts == 5
        assert poison_msg.processing_status == ProcessingStatus.QUARANTINED
        assert poison_msg.ai_processed is False

    # Dispatcher and process_message_batch should now ignore the quarantined message
    res_dispatch = dispatch_message_batches()
    assert res_dispatch == "no_unprocessed_groups"

    res_batch = process_message_batch(str(group.id))
    assert res_batch == "no_unprocessed"


def test_transient_failure_recovers_and_resets_attempts(db, group_and_messages):
    """
    If extraction fails twice but succeeds on the third try:
    - events are created
    - ai_processed is True
    - ai_attempts is reset to 0
    """
    user, group, messages = group_and_messages

    # First fail twice
    with patch("app.services.event_extraction_service.EventExtractionService.extract_batch_via_agnes", return_value=None):
        process_message_batch(str(group.id))
        process_message_batch(str(group.id))

    for msg in messages:
        db.refresh(msg)
        assert msg.ai_attempts == 2
        assert msg.ai_processed is False

    from datetime import datetime
    mock_events = [
        {
            "title": "CSC301 Midterm Exam",
            "event_type": "DEADLINE",
            "course_code": "CSC301",
            "description": "Room 101 at 10 AM",
            "date_time": datetime(2026, 9, 1, 10, 0),
            "needs_review": False,
        }
    ]

    with patch("app.services.event_extraction_service.EventExtractionService.extract_batch_via_agnes", return_value=mock_events):
        with patch("app.services.notification_service.NotificationService.send_event_notification"):
            with patch("app.services.reminder_service.ReminderService.schedule_automatic_reminders"):
                res = process_message_batch(str(group.id))
                assert "processed" in res

    # All messages should now be ai_processed=True with ai_attempts=0
    for msg in messages:
        db.refresh(msg)
        assert msg.ai_processed is True
        assert msg.processing_status == ProcessingStatus.PROCESSED
        assert msg.ai_attempts == 0

    # Event was persisted in DB
    ev = db.query(AcademicEvent).filter(AcademicEvent.group_id == group.id).first()
    assert ev is not None
    assert ev.title == "CSC301 Midterm Exam"


def test_bisect_chain_quarantines_whole_production_batch(db, group_and_messages):
    """A full-size poison batch must end with EVERY message QUARANTINED.

    Regression guard for the bisect-termination bug: the ``ai_attempts <
    batch_max_attempts`` filter was applied to the explicit ``message_ids``
    path as well as the auto-select path, so bisect children stopped loading
    once attempts reached the ceiling. Any batch larger than
    ``2 ** (batch_max_attempts - batch_bisect_after)`` (== 4 with the defaults)
    stalled at ai_attempts == max with processing_status PENDING: excluded from
    selection, never quarantined, and invisible to any operator.

    The 4-message fixture happened to be exactly at that boundary, which is why
    the original tests passed. This test uses a production-sized batch.
    """
    user, group, messages = group_and_messages

    # Grow the fixture to the production batch size so multiple bisect levels
    # are required to reach single messages.
    for i in range(len(messages), 12):
        msg = RawMessage(
            user_id=user.id,
            group_id=group.id,
            message_id=f"msg_{i + 1}",
            sender_jid="sender@s.whatsapp.net",
            message_text=f"Test message {i + 1}",
            ai_processed=False,
            processing_status=ProcessingStatus.PENDING,
            ai_attempts=0,
        )
        db.add(msg)
        messages.append(msg)
    db.commit()

    def run_child(*args, **kwargs):
        """Execute bisect children synchronously so recursion is exercised."""
        return process_message_batch(*args, **kwargs)

    with patch(
        "app.services.event_extraction_service.EventExtractionService.extract_batch_via_agnes",
        return_value=None,
    ):
        with patch.object(process_message_batch, "delay", side_effect=run_child):
            # Drive the dispatcher until it reports nothing left to do. The cap
            # is generous; termination itself is part of what we assert.
            for _ in range(40):
                if dispatch_message_batches() == "no_unprocessed_groups":
                    break

    stuck = []
    for msg in messages:
        db.refresh(msg)
        if msg.processing_status != ProcessingStatus.QUARANTINED:
            stuck.append((msg.message_id, msg.ai_attempts, msg.processing_status))

    assert not stuck, (
        "messages exhausted their attempts without being quarantined "
        "(silently invisible): %r" % stuck
    )

