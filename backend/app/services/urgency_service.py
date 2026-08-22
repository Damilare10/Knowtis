"""
Derived urgency scoring for academic events.

Replaces the keyword-derived ``urgency_score`` (0.5 / 0.8 / 0.9 depending on
whether the words "urgent" or "tomorrow" appeared), which was the dashboard's
primary sort key. Urgency is now a function of time-to-deadline, so an
assignment due in four hours outranks a seminar next month that said "urgent".

Events are duck-typed: anything exposing ``event_type``, ``date_time`` and
``confidence_score`` works, so the ORM model and plain test stubs both pass.
``status`` and ``date_precision`` are read defensively because those columns do
not exist yet (step 5).
"""
from datetime import datetime, timedelta
from typing import Any, Optional

BASE = {"DEADLINE": 1.0, "ALERT": 0.9, "EVENT": 0.7, "INFO": 0.4}
HORIZON_HOURS = 168.0  # one week
ALERT_FLOOR = 0.75
PAST_SCORE = 0.05


def _coerce_enum(value: Any) -> str:
    """Return the string form of an enum member or plain value."""
    if value is None:
        return ""
    return str(getattr(value, "value", value))


def compute_urgency(event: Any, now: Optional[datetime] = None) -> float:
    """Score an event in [0.0, 1.0]. Higher means more urgent."""
    if now is None:
        now = datetime.utcnow()

    event_type = _coerce_enum(getattr(event, "event_type", None)).upper() or "INFO"

    if _coerce_enum(getattr(event, "status", None)).upper() in ("CANCELLED", "CANCELED"):
        return 0.0

    base = BASE.get(event_type, 0.4)
    date_time = getattr(event, "date_time", None)
    precision = _coerce_enum(getattr(event, "date_precision", None)).upper()

    if date_time is None:
        # Unscheduled: type carries the whole signal, and it must rank below a
        # scheduled event of the same type.
        urgency = base * 0.5
    else:
        if precision == "DAY_ONLY":
            # "Friday" must not read as due 00:00 Friday.
            try:
                date_time = date_time.replace(hour=23, minute=59, second=59, microsecond=0)
            except (AttributeError, ValueError):
                pass
        if date_time < now:
            urgency = PAST_SCORE
        else:
            hours_until = (date_time - now).total_seconds() / 3600.0
            decay = max(0.0, min(1.0, 1.0 - hours_until / HORIZON_HOURS))
            urgency = base * 0.4 + decay * 0.6

    confidence = getattr(event, "confidence_score", 0.8)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.8
    confidence = max(0.0, min(1.0, confidence))
    urgency *= 0.7 + 0.3 * confidence

    # The floor is applied AFTER confidence scaling so it actually holds in the
    # returned value. Applying it before let a 0.5-confidence alert land at
    # 0.75 * 0.85 = 0.638, silently defeating the guarantee.
    if event_type == "ALERT" and date_time is not None and date_time >= now:
        urgency = max(urgency, ALERT_FLOOR)

    return round(max(0.0, min(1.0, urgency)), 3)


def recompute_for_user(user_id, db, now: Optional[datetime] = None) -> int:
    """Refresh ``urgency_score`` for one user's live events. Returns the count.

    Bounded to events that are unscheduled or not more than 24h in the past, so
    the work does not grow with account age. Scoring is per-row because urgency
    depends on each event's own ``date_time``; a single SQL expression would need
    a CASE ladder for no real gain at this volume.
    """
    from app.models import AcademicEvent

    if now is None:
        now = datetime.utcnow()
    cutoff = now - timedelta(hours=24)

    events = (
        db.query(AcademicEvent)
        .filter(
            AcademicEvent.user_id == user_id,
            AcademicEvent.is_archived == False,  # noqa: E712
        )
        .filter(
            (AcademicEvent.date_time.is_(None)) | (AcademicEvent.date_time >= cutoff)
        )
        .all()
    )

    updated = 0
    for event in events:
        score = compute_urgency(event, now)
        if event.urgency_score != score:
            event.urgency_score = score
            updated += 1

    if updated:
        db.commit()
    return updated
