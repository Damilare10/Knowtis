"""
Tests for the 3C / 4A wiring inside ``extract_batch_via_agnes``.

Every other test in the suite mocks ``extract_batch_via_agnes`` wholesale, which
means nothing exercised the code under it: the per-message anchor, the
``_source_index`` stamp, or ``TemporalParser.resolve`` being called at all.

These mock only the HTTP boundary (``AgnesService.classify_and_extract_batch``),
so the real wrapping path runs.
"""
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from app.services.event_extraction_service import EventExtractionService


def _msg(text, created_at):
    return {"id": str(uuid.uuid4()), "message_text": text, "created_at": created_at}


def _item(index, **event_overrides):
    event = {
        "action_type": "CREATE",
        "category": "DEADLINE",
        "course_code": "CSC301",
        "title": "CSC301 assignment",
        "description": "Submit via portal",
        "venue": None,
        "date_expression": "tomorrow",
        "date_is_explicit": True,
        "confidence_score": 0.9,
        "relevance_score": 0.8,
        "actionability_score": 0.7,
        "needs_review": False,
        "event_completeness": "complete",
    }
    event.update(event_overrides)
    return {"index": index, "classification": "SIGNAL", "events": [event]}


def _extract(messages, items, anchor=None):
    with patch(
        "app.services.agnes_service.AgnesService.classify_and_extract_batch",
        new=AsyncMock(return_value=items),
    ):
        return EventExtractionService.extract_batch_via_agnes(
            messages, msg_created_at=anchor or messages[0]["created_at"], db=None
        )


# -- per-message anchor (3C) ---------------------------------------------------

def test_tomorrow_resolves_against_each_message_own_timestamp():
    """The batch head anchor must NOT be reused for every message.

    A 15-message batch can span midnight. Both messages here say "tomorrow" and
    were sent exactly 24h apart, so a correct implementation resolves them one
    day apart. If the head anchor leaked to both, the dates would be identical.
    """
    head = datetime(2026, 3, 10, 20, 0, 0)
    messages = [
        _msg("Assignment due tomorrow", head),
        _msg("Another assignment due tomorrow", head + timedelta(hours=24)),
    ]
    events = _extract(messages, [_item(1), _item(2)])

    assert len(events) == 2
    first, second = events[0]["date_time"], events[1]["date_time"]
    assert first is not None and second is not None
    assert (second.date() - first.date()) == timedelta(days=1)


def test_unmappable_index_falls_back_to_the_batch_anchor():
    head = datetime(2026, 3, 10, 20, 0, 0)
    messages = [_msg("Assignment due tomorrow", head)]
    # index 7 does not exist in a 1-message batch.
    events = _extract(messages, [_item(7)])

    assert len(events) == 1
    assert events[0]["date_time"] is not None


# -- source index stamping (3C) -----------------------------------------------

def test_source_index_is_stamped_from_the_model_index():
    head = datetime(2026, 3, 10, 20, 0, 0)
    messages = [
        _msg("First", head),
        _msg("Second", head + timedelta(minutes=1)),
    ]
    events = _extract(messages, [_item(2)])

    assert len(events) == 1
    assert events[0]["_source_index"] == 2


def test_noise_items_produce_no_events():
    head = datetime(2026, 3, 10, 20, 0, 0)
    messages = [_msg("lol", head)]
    items = [{"index": 1, "classification": "NOISE", "events": []}]

    assert _extract(messages, items) == []


def test_one_message_can_yield_multiple_events():
    """A single announcement often carries a deadline AND a cancellation.

    Ported from the old test_extract_events_multi_event, which covered the
    deleted single-message helper.
    """
    head = datetime(2026, 3, 10, 20, 0, 0)
    messages = [_msg("CSC301 assignment due tomorrow, and Friday's lecture is cancelled", head)]
    item = _item(1)
    item["events"].append({
        "action_type": "CANCEL",
        "category": "ALERT",
        "course_code": "CSC301",
        "title": "Friday lecture cancelled",
        "date_expression": "Friday",
        "date_is_explicit": True,
    })

    events = _extract(messages, [item])

    assert len(events) == 2
    assert {e["event_type"] for e in events} == {"DEADLINE", "ALERT"}
    assert {e["action_type"] for e in events} == {"CREATE", "CANCEL"}
    # Both must be attributed to the one source message.
    assert all(e["_source_index"] == 1 for e in events)


# -- date resolution is local, never the model's (4A) -------------------------

def test_model_supplied_resolved_date_is_ignored():
    """A model that still returns an ISO date_time must not be trusted."""
    head = datetime(2026, 3, 10, 20, 0, 0)
    messages = [_msg("Assignment due tomorrow", head)]
    events = _extract(
        messages,
        [_item(1, date_expression="tomorrow", date_time="2020-01-01T09:00:00")],
    )

    assert len(events) == 1
    resolved = events[0]["date_time"]
    assert resolved is not None
    assert resolved.year == 2026, "the model's own ISO date leaked through"


def test_model_supplied_urgency_never_survives_wrapping():
    head = datetime(2026, 3, 10, 20, 0, 0)
    messages = [_msg("Assignment due tomorrow", head)]
    events = _extract(messages, [_item(1, urgency_score=0.99)])

    assert len(events) == 1
    assert "urgency_score" not in events[0]


def test_day_only_expression_does_not_fabricate_a_time():
    head = datetime(2026, 3, 10, 20, 0, 0)
    messages = [_msg("Assignment due tomorrow", head)]
    events = _extract(messages, [_item(1, date_expression="tomorrow")])

    assert events[0]["date_precision"] == "day_only"


def test_explicit_time_yields_exact_precision():
    head = datetime(2026, 3, 10, 20, 0, 0)
    messages = [_msg("Lecture tomorrow 2pm", head)]
    events = _extract(
        messages, [_item(1, category="EVENT", date_expression="tomorrow 2pm")]
    )

    assert events[0]["date_precision"] == "exact"


def test_vague_expression_resolves_to_nothing_and_forces_review():
    """"soon" must not become a date, and an unresolved deadline needs review."""
    head = datetime(2026, 3, 10, 20, 0, 0)
    messages = [_msg("Assignment due soon", head)]
    events = _extract(
        messages,
        [_item(1, date_expression="soon", date_is_explicit=False, needs_review=False)],
    )

    assert len(events) == 1
    assert events[0]["date_time"] is None
    assert events[0]["date_precision"] == "unknown"
    assert events[0]["needs_review"] is True


def test_non_explicit_date_forces_review_even_when_resolvable():
    head = datetime(2026, 3, 10, 20, 0, 0)
    messages = [_msg("Assignment due tomorrow", head)]
    events = _extract(
        messages,
        [_item(1, date_expression="tomorrow", date_is_explicit=False, needs_review=False)],
    )

    assert events[0]["needs_review"] is True


def test_extraction_failure_is_distinguishable_from_all_noise():
    """None means retry, [] means genuinely no events. Callers branch on this."""
    head = datetime(2026, 3, 10, 20, 0, 0)
    messages = [_msg("Assignment due tomorrow", head)]

    assert _extract(messages, None) is None
    assert _extract(messages, []) == []
