"""
Unit tests for the surviving classification surface.

This file replaces the old ``test_classifier.py``, which exercised the local
keyword/SetFit classifier and the legacy extractor that step 4C deleted. Every
original assertion was ported rather than dropped:

* signal/noise classification    -> now Agnes's job. Covered end to end by
  ``test_batch_extraction_wiring.py`` (NOISE items yield no events) and
  ``test_pipeline_integration.py`` (survivors reach extraction).
* bare temporal fragments        -> ported below to the prefilter as
  ``SKIPPED_FRAGMENT``, which is what now stops "4pm tomorrow" becoming an event.
* ``calculate_scores`` bounds     -> ported below to derived urgency, which
  replaced the keyword scorer. Depth lives in ``test_urgency_service.py``.
* temporal resolution            -> the ~170-case corpus in
  ``tests/fixtures/temporal_cases.py`` via ``test_temporal_parser.py``.
* taxonomy mapping, schema validation, anchor formatting, course-code
  normalisation -> kept here, unchanged in intent.
"""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import ProcessingStatus, WhatsAppGroup
from app.services.classifier_service import (
    CATEGORY_MAP,
    Classification,
    ClassifierCategory,
    EventCategory,
    MessageClassifier,
)
from app.services.event_extraction_service import EventExtractionService
from app.services.prefilter import classify_skip
from app.services.urgency_service import compute_urgency


# ── Taxonomy (kept surface) ───────────────────────────────────────────────────

def test_category_to_classifier_mapping():
    assert MessageClassifier.category_to_classifier("exam") == ClassifierCategory.DEADLINE
    assert MessageClassifier.category_to_classifier("lecture_update") == ClassifierCategory.ALERT
    assert MessageClassifier.category_to_classifier("fee_notice") == ClassifierCategory.DEADLINE
    assert MessageClassifier.category_to_classifier("noise") == ClassifierCategory.NOISE


def test_unknown_category_falls_back_to_info_not_noise():
    """Mislabelling an announcement as noise loses a deadline; INFO is untidy."""
    assert MessageClassifier.category_to_classifier("something_new") == ClassifierCategory.INFO
    assert MessageClassifier.category_to_classifier("") == ClassifierCategory.INFO
    assert MessageClassifier.category_to_classifier(None) == ClassifierCategory.INFO


def test_category_map_covers_every_non_noise_label():
    non_noise = set(ClassifierCategory) - {ClassifierCategory.NOISE}
    assert set(CATEGORY_MAP) == non_noise
    for label, (classification, event_category) in CATEGORY_MAP.items():
        assert classification is Classification.SIGNAL
        assert event_category.value == label.value


# ── Bare fragments: ported from TestEventExtractionBareFragment ───────────────

@pytest.fixture(name="db")
def db_fixture():
    """Local session, mirroring test_prefilter.py, to avoid the pre-existing
    JSONB/SQLite incompatibility in WhatsAppAuthState."""
    from sqlalchemy import JSON

    from app.models import WhatsAppAuthState

    engine = create_engine(
        "sqlite:///./test_classifier_surface.db",
        connect_args={"check_same_thread": False},
    )
    WhatsAppAuthState.__table__.c.state.type = JSON()

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(name="group")
def group_fixture(db):
    group = WhatsAppGroup(
        user_id=uuid.uuid4(),
        group_jid=f"1203630{uuid.uuid4().hex[:8]}@g.us",
        group_name="Test Group",
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@pytest.mark.parametrize(
    "text",
    [
        "4pm tomorrow",
        "tomorrow",
        "12/06/2024",
        "next Friday",
        "2:30 pm",
    ],
)
def test_bare_temporal_fragments_are_skipped(db, group, text):
    """A date with no announcement attached must never reach the LLM.

    Previously enforced by ``_is_bare_fragment`` inside the legacy extractor;
    now enforced deterministically and far more cheaply by the prefilter.
    """
    assert classify_skip(text, group.id, db) == ProcessingStatus.SKIPPED_FRAGMENT


@pytest.mark.parametrize(
    "text",
    [
        "CSC 301 quiz cancelled tomorrow",
        "ELE310 exam next Monday",
        "CSC 301 assignment due tomorrow",
        "The CSC 301 quiz scheduled for tomorrow has been moved to Thursday.",
    ],
)
def test_real_short_announcements_survive_the_prefilter(db, group, text):
    """Recall matters more than precision: a false skip loses a deadline."""
    assert classify_skip(text, group.id, db) is None


def test_terse_announcement_is_rescued_by_its_action_verb(db, group):
    """"Class cancelled" is 2 tokens but is a genuine alert."""
    assert classify_skip("Class cancelled", group.id, db) is None


def test_empty_and_emoji_only_messages_are_skipped(db, group):
    assert classify_skip("", group.id, db) == ProcessingStatus.SKIPPED_EMPTY
    assert classify_skip("   ", group.id, db) == ProcessingStatus.SKIPPED_EMPTY
    assert classify_skip("\U0001f602\U0001f602", group.id, db) == ProcessingStatus.SKIPPED_EMPTY


# ── Score bounds: ported from test_calculate_scores ──────────────────────────

def test_derived_urgency_stays_in_unit_range():
    """The keyword scorer's only real guarantee was 0 <= score <= 1.

    Urgency is now derived from time-to-deadline. The bound still holds, and it
    no longer depends on the words "urgent" or "tomorrow" appearing.
    """
    now = datetime(2026, 3, 10, 12, 0, 0)

    class _Stub:
        def __init__(self, event_type, date_time, confidence_score=0.9):
            self.event_type = event_type
            self.date_time = date_time
            self.confidence_score = confidence_score

    cases = [
        _Stub("DEADLINE", now.replace(hour=13)),
        _Stub("DEADLINE", None),
        _Stub("ALERT", now.replace(hour=23)),
        _Stub("EVENT", datetime(2026, 9, 1)),
        _Stub("INFO", datetime(2020, 1, 1)),
        _Stub("INFO", None, confidence_score=0.0),
    ]
    for stub in cases:
        assert 0.0 <= compute_urgency(stub, now) <= 1.0


def test_urgency_ignores_the_word_urgent():
    """The old scorer keyed on "urgent"; the new one must not."""
    now = datetime(2026, 3, 10, 12, 0, 0)

    class _Stub:
        event_type = "EVENT"
        confidence_score = 0.9

        def __init__(self, title):
            self.title = title
            self.date_time = datetime(2026, 4, 20, 10, 0, 0)

    plain = compute_urgency(_Stub("Seminar on AI"), now)
    shouty = compute_urgency(_Stub("URGENT!! Seminar on AI"), now)
    assert plain == shouty


# ── Structured AI schemas (kept, plus the deprecation contract) ───────────────

def test_pydantic_ai_schemas_validation():
    from app.schemas import BatchMessageAIResponse, SingleMessageAIResponse

    raw_single_json = """
    {
        "classification": "SIGNAL",
        "events": [
            {
                "category": "DEADLINE",
                "course_code": "CSC301",
                "title": "CSC301 Lab Report Due",
                "description": "Lab report 2 due Friday by 5pm",
                "date_expression": "Friday by 5pm",
                "date_is_explicit": true
            }
        ]
    }
    """
    parsed = SingleMessageAIResponse.model_validate_json(raw_single_json)
    assert parsed.classification == "SIGNAL"
    assert len(parsed.events) == 1
    assert parsed.events[0].course_code == "CSC301"
    assert parsed.events[0].date_expression == "Friday by 5pm"
    assert parsed.events[0].date_is_explicit is True

    raw_batch_json = """
    {
        "items": [
            {
                "index": 1,
                "classification": "SIGNAL",
                "events": [
                    {
                        "category": "ALERT",
                        "course_code": "ELE310",
                        "title": "Class canceled"
                    }
                ]
            }
        ]
    }
    """
    batch_parsed = BatchMessageAIResponse.model_validate_json(raw_batch_json)
    assert len(batch_parsed.items) == 1
    assert batch_parsed.items[0].events[0].course_code == "ELE310"


def test_deprecated_resolved_date_time_still_validates():
    """A model running the OLD prompt must not hard-fail for one release.

    ``date_time`` is accepted and ignored; ``_wrap_batch_result`` logs when it
    appears. Without this tolerance, a stale prompt would turn every response
    into a parse failure and every batch into a retry.
    """
    from app.schemas import SingleMessageAIResponse

    parsed = SingleMessageAIResponse.model_validate_json(
        '{"classification": "SIGNAL", "events": [{"category": "DEADLINE",'
        ' "title": "Old shape", "date_time": "2026-07-31T17:00:00Z"}]}'
    )
    assert parsed.events[0].date_time == "2026-07-31T17:00:00Z"
    assert parsed.events[0].date_expression is None


# ── Anchor formatting and course codes (kept) ────────────────────────────────

def test_anchor_timestamp_day_of_week_formatting():
    from app.services.agnes_service import AgnesService

    dt = datetime(2026, 7, 29, 18, 43, 30, tzinfo=timezone.utc)
    formatted = AgnesService._format_anchor_timestamp(dt)
    assert "Wednesday" in formatted
    assert "Day of week: Wednesday" in formatted


def test_align_course_code():
    assert EventExtractionService.align_course_code(" csc  301 ") == "CSC301"
    assert EventExtractionService.align_course_code("mth-201") == "MTH201"
    assert EventExtractionService.align_course_code("") is None
    assert EventExtractionService.align_course_code(None) is None
