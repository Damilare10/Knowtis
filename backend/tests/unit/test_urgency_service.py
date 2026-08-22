"""
Tests for derived urgency scoring (pipeline step 6).
"""
import datetime
from types import SimpleNamespace

import pytest

from app.services.urgency_service import ALERT_FLOOR, compute_urgency

NOW = datetime.datetime(2026, 1, 1, 12, 0, 0)


def make_event(event_type, hours_until, confidence=0.8, date_precision=None, status=None):
    return SimpleNamespace(
        event_type=event_type,
        date_time=None if hours_until is None else NOW + datetime.timedelta(hours=hours_until),
        confidence_score=confidence,
        status=status,
        date_precision=date_precision,
    )


def test_imminent_deadline_outranks_distant_confident_event():
    """The defect this step exists to fix: time-to-deadline must beat keywords."""
    soon = make_event("DEADLINE", hours_until=4, confidence=0.7)
    distant = make_event("EVENT", hours_until=24 * 30, confidence=0.95)
    assert compute_urgency(soon, NOW) > compute_urgency(distant, NOW)


def test_cancelled_scores_zero():
    for status in ("CANCELLED", "cancelled", "Canceled"):
        ev = make_event("DEADLINE", hours_until=5, status=status)
        assert compute_urgency(ev, NOW) == 0.0


def test_unscheduled_ranks_below_scheduled_same_type():
    unscheduled = make_event("DEADLINE", hours_until=None)
    scheduled = make_event("DEADLINE", hours_until=48)
    assert compute_urgency(unscheduled, NOW) < compute_urgency(scheduled, NOW)


@pytest.mark.parametrize("confidence", [0.0, 0.3, 0.5, 0.8, 1.0])
@pytest.mark.parametrize("hours_until", [1, 24, 168, 500])
def test_alert_floor_holds_after_confidence_scaling(confidence, hours_until):
    """Regression guard: the floor was applied before confidence scaling, so a
    low-confidence alert landed at 0.75 * 0.85 = 0.638 and the guarantee was
    silently defeated."""
    ev = make_event("ALERT", hours_until=hours_until, confidence=confidence)
    assert compute_urgency(ev, NOW) >= ALERT_FLOOR


def test_past_alert_is_not_floored():
    """A finished alert should sink, not stay pinned at the floor."""
    ev = make_event("ALERT", hours_until=-5)
    assert compute_urgency(ev, NOW) < ALERT_FLOOR


def test_past_event_sinks():
    ev = make_event("DEADLINE", hours_until=-5)
    assert compute_urgency(ev, NOW) == round(0.05 * (0.7 + 0.3 * 0.8), 3)


def test_closer_deadline_always_scores_higher():
    scores = [compute_urgency(make_event("DEADLINE", h), NOW) for h in (2, 12, 48, 120, 400)]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.parametrize("event_type", ["DEADLINE", "ALERT", "EVENT", "INFO"])
@pytest.mark.parametrize("hours_until", [None, -10, 0, 2, 24, 168, 500])
def test_output_always_in_range(event_type, hours_until):
    ev = make_event(event_type, hours_until, confidence=0.6)
    assert 0.0 <= compute_urgency(ev, NOW) <= 1.0


def test_day_only_treated_as_end_of_day():
    """A DAY_ONLY event dated tomorrow must not read as due at 00:00."""
    midnight_tomorrow = datetime.datetime(2026, 1, 2, 0, 0, 0)
    day_only = SimpleNamespace(
        event_type="DEADLINE", date_time=midnight_tomorrow,
        confidence_score=1.0, status=None, date_precision="DAY_ONLY",
    )
    exact = SimpleNamespace(
        event_type="DEADLINE", date_time=midnight_tomorrow,
        confidence_score=1.0, status=None, date_precision=None,
    )
    # End-of-day pushes the deadline further out, so urgency is lower.
    assert compute_urgency(day_only, NOW) < compute_urgency(exact, NOW)


def test_enum_like_event_type_is_accepted():
    """Works with SQLAlchemy enum members, not just plain strings."""
    ev = make_event(SimpleNamespace(value="DEADLINE"), hours_until=4)
    plain = make_event("DEADLINE", hours_until=4)
    assert compute_urgency(ev, NOW) == compute_urgency(plain, NOW)


def test_missing_confidence_defaults_and_does_not_raise():
    ev = SimpleNamespace(event_type="DEADLINE", date_time=NOW + datetime.timedelta(hours=4))
    assert 0.0 <= compute_urgency(ev, NOW) <= 1.0
