"""
Unit tests for step 5 deduplication and reconciliation rewrite.

Covers:
1. Exact business-key duplicate detection (user_id, course_code, event_type, date(date_time))
2. Vector similarity fallback when business key is incomplete
3. Non-merge of distinct items ("Assignment 1" vs "Assignment 2") at threshold 0.92
4. State-machine cancellation setting status = CANCELLED, dismissing reminders, leaving title clean
5. State-machine update targeting by date proximity (within ±7 days) rather than blind recency
6. Tolerance for extra payload keys in reconcile_event
"""
import uuid
import pytest
from datetime import datetime, timedelta, timezone
from app.models import (
    AcademicEvent, EventStatus, EventDatePrecision, EventType,
    Reminder, ReminderState, User, WhatsAppGroup
)
from app.services.deduplication_service import DeduplicationService
from app.utils import generate_embedding


@pytest.fixture
def test_user(db):
    u = User(
        id=uuid.uuid4(),
        email=f"dedup_test_{uuid.uuid4().hex[:8]}@example.com",
        username=f"dedup_user_{uuid.uuid4().hex[:8]}",
        full_name="Dedup User",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def test_group(db, test_user):
    g = WhatsAppGroup(
        id=uuid.uuid4(),
        user_id=test_user.id,
        group_jid=f"{uuid.uuid4().hex[:12]}@g.us",
        group_name="CSC301 Class Group",
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


def test_business_key_hit_matches_duplicate(db, test_user, test_group):
    """Exact match on (user_id, course_code, event_type, date(date_time)) matches immediately."""
    dt = datetime(2026, 9, 15, 14, 0, 0)
    existing = AcademicEvent(
        id=uuid.uuid4(),
        user_id=test_user.id,
        group_id=test_group.id,
        event_type=EventType.DEADLINE,
        course_code="CSC301",
        title="CSC301 Assignment 1 Due",
        date_time=dt,
        status=EventStatus.ACTIVE,
        date_precision=EventDatePrecision.EXACT,
    )
    db.add(existing)
    db.commit()

    hit = DeduplicationService.find_duplicate(
        user_id=test_user.id,
        new_event_text="CSC301 Assignment 1 submission deadline",
        group_id=test_group.id,
        db=db,
        course_code="CSC301",
        event_type="DEADLINE",
        date_time=dt,
    )
    assert hit is not None
    assert hit.id == existing.id


def test_vector_fallback_when_business_key_incomplete(db, test_user, test_group, monkeypatch):
    """When date_time or course_code is missing, vector similarity fallback identifies the duplicate."""
    # Synthetic embeddings with high similarity
    emb_a = [1.0, 0.0, 0.0] + [0.0] * 381
    emb_b = [0.99, 0.01, 0.0] + [0.0] * 381

    existing = AcademicEvent(
        id=uuid.uuid4(),
        user_id=test_user.id,
        group_id=test_group.id,
        event_type=EventType.INFO,
        course_code=None,
        title="Departmental meeting next week",
        date_time=None,
        embedding=str(emb_a),
        status=EventStatus.ACTIVE,
    )
    db.add(existing)
    db.commit()

    # Monkeypatch generate_embedding to return emb_b
    monkeypatch.setattr("app.services.deduplication_service.generate_embedding", lambda text: emb_b)

    hit = DeduplicationService.find_duplicate(
        user_id=test_user.id,
        new_event_text="Departmental meeting coming up next week",
        group_id=test_group.id,
        db=db,
        threshold=0.92,
        course_code=None,
        date_time=None,
        event_type="INFO",
    )
    assert hit is not None
    assert hit.id == existing.id


def test_assignment_1_and_assignment_2_do_not_merge(db, test_user, test_group, monkeypatch):
    """'CSC301 Assignment 1' and 'CSC301 Assignment 2' must NOT merge at threshold 0.92."""
    import math
    sim_88_x = math.cos(math.radians(28.5))
    sim_88_y = math.sin(math.radians(28.5))
    emb_a1 = [1.0, 0.0] + [0.0] * 382
    emb_a2 = [sim_88_x, sim_88_y] + [0.0] * 382

    existing = AcademicEvent(
        id=uuid.uuid4(),
        user_id=test_user.id,
        group_id=test_group.id,
        event_type=EventType.DEADLINE,
        course_code="CSC301",
        title="CSC301 Assignment 1",
        date_time=None,  # Incomplete business key forces vector check
        embedding=str(emb_a1),
        status=EventStatus.ACTIVE,
    )
    db.add(existing)
    db.commit()

    monkeypatch.setattr("app.services.deduplication_service.generate_embedding", lambda text: emb_a2)

    hit = DeduplicationService.find_duplicate(
        user_id=test_user.id,
        new_event_text="CSC301 Assignment 2",
        group_id=test_group.id,
        db=db,
        threshold=0.92,
        course_code="CSC301",
        date_time=None,
        event_type="DEADLINE",
    )
    assert hit is None, "Assignment 2 with similarity below 0.92 must not merge with Assignment 1"


def test_reconcile_event_cancellation_sets_status_and_cleans_title(db, test_user, test_group):
    """CANCEL action sets status = CANCELLED, cancels reminders, leaves title clean, and writes revision."""
    dt = datetime(2026, 9, 20, 10, 0, 0)
    event = AcademicEvent(
        id=uuid.uuid4(),
        user_id=test_user.id,
        group_id=test_group.id,
        event_type=EventType.EVENT,
        course_code="MTH201",
        title="MTH201 Tutorial Session",
        date_time=dt,
        status=EventStatus.ACTIVE,
    )
    db.add(event)
    db.flush()

    reminder = Reminder(
        id=uuid.uuid4(),
        user_id=test_user.id,
        event_id=event.id,
        scheduled_time=dt - timedelta(hours=2),
        is_active=True,
    )
    db.add(reminder)
    db.commit()

    event_data = {
        "action_type": "CANCEL",
        "course_code": "MTH201",
        "event_type": "EVENT",
        "date_time": dt,
        "description": "Tutorial cancelled due to lecturer illness",
        "source_message_id": "msg-12345",
        "date_precision": "exact",  # extra key test
    }

    target, outcome = DeduplicationService.reconcile_event(
        user_id=test_user.id,
        event_data=event_data,
        group_id=test_group.id,
        db=db,
    )

    assert outcome == "CANCELLED"
    assert target.id == event.id
    assert target.status == EventStatus.CANCELLED
    # Title must remain clean — NOT "[CANCELLED] MTH201 Tutorial Session"
    assert target.title == "MTH201 Tutorial Session"
    assert not target.title.startswith("[CANCELLED]")

    # Reminder must be deactivated and event reminder_state DISMISSED
    db.refresh(reminder)
    assert reminder.is_active is False
    assert target.reminder_state == ReminderState.DISMISSED

    # Revision must be recorded
    assert target.revisions is not None
    assert len(target.revisions) == 1
    assert target.revisions[0]["action"] == "CANCEL"
    assert target.revisions[0]["source_message_id"] == "msg-12345"


def test_reconcile_event_update_targets_nearest_date_and_records_revisions(db, test_user, test_group):
    """UPDATE targets the event within ±7 days of incoming date rather than the newest row."""
    now = datetime.utcnow()
    # Event 1: distant past (20 days ago)
    dt1 = now - timedelta(days=20)
    ev1 = AcademicEvent(
        id=uuid.uuid4(),
        user_id=test_user.id,
        group_id=test_group.id,
        event_type=EventType.EVENT,
        course_code="PHY101",
        title="PHY101 Lab",
        venue="Lab 1",
        date_time=dt1,
        status=EventStatus.ACTIVE,
        created_at=now - timedelta(days=5),
    )
    # Event 2: upcoming in 2 days
    dt2 = now + timedelta(days=2)
    ev2 = AcademicEvent(
        id=uuid.uuid4(),
        user_id=test_user.id,
        group_id=test_group.id,
        event_type=EventType.EVENT,
        course_code="PHY101",
        title="PHY101 Lab",
        venue="Lab 1",
        date_time=dt2,
        status=EventStatus.ACTIVE,
        created_at=now - timedelta(days=10),  # Older created_at, but date_time matches
    )
    db.add_all([ev1, ev2])
    db.commit()

    # Incoming update for the upcoming lab (date is dt2 + 1 hour)
    incoming_dt = dt2 + timedelta(hours=1)
    event_data = {
        "action_type": "UPDATE",
        "course_code": "PHY101",
        "event_type": "EVENT",
        "date_time": incoming_dt,
        "venue": "Physics Hall A",
        "description": "Moved to Hall A",
        "source_message_id": "msg-update-99",
    }

    target, outcome = DeduplicationService.reconcile_event(
        user_id=test_user.id,
        event_data=event_data,
        group_id=test_group.id,
        db=db,
    )

    assert outcome == "UPDATED"
    assert target.id == ev2.id  # Targeted ev2 because of ±7d proximity to dt2
    assert target.venue == "Physics Hall A"
    assert target.date_time == incoming_dt
    assert len(target.revisions) == 1
    assert target.revisions[0]["action"] == "UPDATE"
    assert target.revisions[0]["source_message_id"] == "msg-update-99"
