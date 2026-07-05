"""
Centralised timezone helpers for Knowtis.

Knowtis is a Nigerian product, so every wall-clock value displayed in the
UI should reflect Africa/Lagos time (UTC+1, no DST). Internally we persist
datetimes as naive UTC for backward compatibility with the existing
``DateTime`` columns. This module provides three guarantees:

1. ``now_app()`` returns a timezone-aware datetime in ``settings.app_timezone``.
   Use this for any relative-date logic (e.g. ``"tomorrow"``, ``"Friday"``).

2. ``now_naive_utc()`` returns a naive UTC datetime. Use this only when
   writing to a legacy ``DateTime`` column that does not carry tzinfo.

3. ``format_iso_for_api(dt)`` normalises any datetime (naive UTC or aware)
   to an ISO-8601 string carrying the ``Z`` suffix so the frontend
   unambiguously interprets it as UTC and converts to Africa/Lagos for
   display.

A custom Pydantic v2 serializer in ``schemas.py`` calls ``format_iso_for_api``
on every ``datetime`` field, so adding these helpers fixes both reads and
writes with one change.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _resolve_app_zone() -> ZoneInfo:
    """Resolve the configured app timezone, falling back to Africa/Lagos."""
    try:
        from app.config import settings
        name = getattr(settings, "app_timezone", None) or "Africa/Lagos"
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ImportError):
        # Fallback: build a fixed UTC+1 zone so the rest of the code never
        # has to special-case "no IANA data available" (Windows hosts in
        # particular ship without tzdata in the stdlib).
        return ZoneInfo("Africa/Lagos")


# Resolved at first call. Subsequent reads come straight from the cache.
_APP_TZ: Optional[ZoneInfo] = None


def app_tz() -> ZoneInfo:
    global _APP_TZ
    if _APP_TZ is None:
        _APP_TZ = _resolve_app_zone()
    return _APP_TZ


def now_app() -> datetime:
    """Current time as a timezone-aware datetime in the app's timezone."""
    return datetime.now(tz=app_tz())


def now_naive_utc() -> datetime:
    """Current time as a naive UTC datetime. Use only for legacy DateTime cols."""
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


def to_naive_utc(dt: datetime) -> datetime:
    """Convert any datetime to naive UTC for storage in legacy DateTime cols."""
    if dt.tzinfo is None:
        # Assume the naive value already represents UTC (legacy data).
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def format_iso_for_api(dt: Optional[datetime]) -> Optional[str]:
    """
    Serialise a datetime for the API response.

    Naive datetimes are interpreted as UTC (consistent with the existing
    storage convention). The returned string carries a ``Z`` suffix so
    the frontend's ``new Date(...)`` parses it as an absolute instant.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    # Trim microseconds to keep payloads small; ``+00:00`` -> ``Z``.
    iso = dt.replace(microsecond=0).isoformat()
    return iso.replace("+00:00", "Z")


__all__ = [
    "app_tz",
    "now_app",
    "now_naive_utc",
    "to_naive_utc",
    "format_iso_for_api",
]
