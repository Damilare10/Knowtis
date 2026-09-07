"""
Unit Tests - Deterministic Prefilter
"""
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.models import ProcessingStatus, RawMessage, WhatsAppGroup
from app.services.prefilter import classify_skip


@pytest.fixture(name="db")
def db_fixture():
    """Override conftest's db fixture to avoid the pre-existing JSONB/SQLite
    incompatibility in WhatsAppAuthState.  Creates only the tables needed by
    the prefilter tests."""
    from sqlalchemy import event

    engine = create_engine(
        "sqlite:///./test_prefilter.db",
        connect_args={"check_same_thread": False},
    )

        # Patch JSONB -> JSON before table creation so SQLite can handle it.
    from app.models import WhatsAppAuthState
    from sqlalchemy import JSON
    WhatsAppAuthState.__table__.c.state.type = JSON()

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app import models  # noqa
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def _make_group(db, user_id=None) -> WhatsAppGroup:
    uid = user_id or uuid.uuid4()
    group = WhatsAppGroup(
        user_id=uid,
        group_jid=f"1203630{uuid.uuid4().hex[:8]}@g.us",
        group_name="Test Group",
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


def _make_repeat(db, group: WhatsAppGroup, text: str, created_at=None) -> None:
    """Insert a RawMessage with the same normalised text_hash as *text*."""
    import hashlib

    normalized = " ".join(text.lower().split())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    msg = RawMessage(
        user_id=group.user_id,
        group_id=group.id,
        message_id=f"repeat-{uuid.uuid4().hex}",
        sender_jid="2348012345678@s.whatsapp.net",
        sender_name="Rep",
        message_text=text,
        text_hash=digest,
        processing_status=ProcessingStatus.PROCESSED,
    )
    if created_at is not None:
        msg.created_at = created_at
    db.add(msg)
    db.commit()


# ── Rule 1: SKIPPED_EMPTY ────────────────────────────────────────────────────

def test_empty_string_is_skipped_empty(db):
    group = _make_group(db)
    result = classify_skip("", group.id, db)
    assert result == ProcessingStatus.SKIPPED_EMPTY


def test_whitespace_only_is_skipped_empty(db):
    group = _make_group(db)
    result = classify_skip("   \t\n  ", group.id, db)
    assert result == ProcessingStatus.SKIPPED_EMPTY


def test_emoji_only_is_skipped_empty(db):
    group = _make_group(db)
    result = classify_skip("😂😂😂", group.id, db)
    assert result == ProcessingStatus.SKIPPED_EMPTY


def test_non_empty_text_passes_rule_1(db):
    group = _make_group(db)
    result = classify_skip("hello world my friend", group.id, db)
    assert result is None


# ── Rule 2: SKIPPED_FRAGMENT ─────────────────────────────────────────────────

def test_single_token_no_verb_is_fragment(db):
    group = _make_group(db)
    result = classify_skip("hello", group.id, db)
    assert result == ProcessingStatus.SKIPPED_FRAGMENT


def test_two_tokens_no_verb_is_fragment(db):
    group = _make_group(db)
    result = classify_skip("hello there", group.id, db)
    assert result == ProcessingStatus.SKIPPED_FRAGMENT


def test_three_tokens_no_verb_is_fragment(db):
    group = _make_group(db)
    result = classify_skip("hello there friend", group.id, db)
    assert result == ProcessingStatus.SKIPPED_FRAGMENT


def test_exactly_four_tokens_no_verb_passes(db):
    """Boundary: exactly 4 tokens with no action verb should NOT be skipped."""
    group = _make_group(db)
    result = classify_skip("hello there my friend", group.id, db)
    assert result is None


def test_two_tokens_with_action_verb_passes(db):
    """A 2-token message containing an action verb must pass."""
    group = _make_group(db)
    result = classify_skip("Class cancelled", group.id, db)
    assert result is None


def test_three_tokens_with_action_verb_passes(db):
    group = _make_group(db)
    result = classify_skip("Exam moved tomorrow", group.id, db)
    assert result is None


def test_action_verb_requires_word_boundary(db):
    """'shifting' is not in ACTION_VERBS — verify no substring false match."""
    group = _make_group(db)
    result = classify_skip("been shifting", group.id, db)
    # 2 tokens, "shifting" not in ACTION_VERBS -> fragment.
    # The regression assertion: we don't match "hi" inside "shifting".
    assert result == ProcessingStatus.SKIPPED_FRAGMENT


# ── Rule 3: SKIPPED_REPEAT ───────────────────────────────────────────────────

def test_same_text_same_group_within_24h_is_repeat(db):
    group = _make_group(db)
    _make_repeat(db, group, "Assignment due Friday")
    result = classify_skip("Assignment due Friday", group.id, db)
    assert result == ProcessingStatus.SKIPPED_REPEAT


def test_same_text_same_group_after_24h_passes(db):
    group = _make_group(db)
    old_time = datetime.utcnow() - timedelta(hours=25)
    _make_repeat(db, group, "Assignment due Friday", created_at=old_time)
    result = classify_skip("Assignment due Friday", group.id, db)
    assert result is None


def test_same_text_different_group_passes(db):
    """Same text_hash in a DIFFERENT group must NOT be skipped."""
    group_a = _make_group(db)
    group_b = _make_group(db)
    _make_repeat(db, group_a, "Venue changed to Hall B")
    result = classify_skip("Venue changed to Hall B", group_b.id, db)
    assert result is None


def test_different_text_same_group_passes(db):
    group = _make_group(db)
    _make_repeat(db, group, "Original message text")
    result = classify_skip("Completely different message here now", group.id, db)
    assert result is None


# ── Regression: question-form announcements must pass ────────────────────────

def test_question_form_announcement_passes(db):
    """Course reps write 'Class has moved to Hall B, ok?' — must not drop."""
    group = _make_group(db)
    result = classify_skip("Class has moved to Hall B, ok?", group.id, db)
    assert result is None


# ── Regression: substring matching must not cause false positives ────────────

def test_shifted_does_not_false_match_hi(db):
    """'shifted' contains 'hi' as substring — old noise check bug."""
    group = _make_group(db)
    # 2 tokens, "shifted" IS an action verb -> passes (not skipped).
    result = classify_skip("been shifted", group.id, db)
    assert result is None


def test_check_does_not_false_match_k(db):
    """'check' contains 'k' as substring — old noise check bug."""
    group = _make_group(db)
    # 3 tokens, no action verb -> fragment (but NOT because 'k' matched).
    result = classify_skip("please check now", group.id, db)
    assert result == ProcessingStatus.SKIPPED_FRAGMENT


def test_whitespace_normalisation_consistent_with_ingest(db):
    """Hash must be identical regardless of whitespace/case variations."""
    import hashlib

    variants = [
        "Assignment due Friday",
        "  assignment   due   friday  ",
        "ASSIGNMENT DUE FRIDAY",
        "assignment\tdue\nfriday",
    ]
    expected = hashlib.sha256("assignment due friday".encode("utf-8")).hexdigest()
    for variant in variants:
        normalized = " ".join(variant.lower().split())
        actual = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        assert actual == expected


# -- Regression: self-match on the real call site -----------------------------

def test_persisted_message_is_not_a_repeat_of_itself(db):
    """The batch writer classifies rows the listener ALREADY stored, hash included.

    Without exclude_message_id the repeat check matched the row against itself,
    so every message in production would have been reported SKIPPED_REPEAT and
    the prefilter would have dropped 100% of traffic. The original suite missed
    this because it only ever classified text that was not yet in the table.
    """
    from app.services.prefilter import compute_text_hash

    group = _make_group(db)
    body = "Assignment due Friday in Hall B"
    persisted = RawMessage(
        user_id=group.user_id,
        group_id=group.id,
        message_id="self-" + uuid.uuid4().hex[:8],
        message_text=body,
        text_hash=compute_text_hash(body),
        processing_status=ProcessingStatus.PENDING,
        created_at=datetime.utcnow(),
    )
    db.add(persisted)
    db.commit()

    assert classify_skip(body, group.id, db, exclude_message_id=persisted.id) is None
    # Sanity: without the exclusion it self-matches, which is the bug.
    assert classify_skip(body, group.id, db) == ProcessingStatus.SKIPPED_REPEAT


def test_second_identical_message_is_still_a_repeat(db):
    """Exclusion must only skip the row itself, not disable repeat detection."""
    from app.services.prefilter import compute_text_hash

    group = _make_group(db)
    body = "Assignment due Friday in Hall B"
    rows = []
    for i in range(2):
        row = RawMessage(
            user_id=group.user_id,
            group_id=group.id,
            message_id=f"dup-{i}-" + uuid.uuid4().hex[:6],
            message_text=body,
            text_hash=compute_text_hash(body),
            processing_status=ProcessingStatus.PENDING,
            created_at=datetime.utcnow(),
        )
        db.add(row)
        rows.append(row)
    db.commit()

    assert classify_skip(body, group.id, db, exclude_message_id=rows[1].id) == (
        ProcessingStatus.SKIPPED_REPEAT
    )


def test_shared_hash_contract_matches_listener():
    """One hash function, not two. Drift here silently breaks repeat detection."""
    from app.services.prefilter import compute_text_hash, normalise_for_hash

    assert normalise_for_hash("  Assignment   DUE\tFriday  ") == "assignment due friday"
    assert compute_text_hash("Assignment due Friday") == compute_text_hash(
        "  ASSIGNMENT   due\nfriday "
    )
    assert compute_text_hash("   ") is None
