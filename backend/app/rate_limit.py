"""
Shared rate limiting setup.
Routes can safely import ``limiter`` even when slowapi is not installed.
"""
import logging
from datetime import datetime, date
from threading import Lock
from typing import Dict, Tuple

from fastapi import HTTPException, status

from app.config import settings
from app.utils import resolve_user_tier


logger = logging.getLogger(__name__)


class NoopLimiter:
    """Fallback limiter that leaves route handlers unchanged in dev/test."""

    def limit(self, *_args, **_kwargs):
        def decorator(func):
            return func

        return decorator


try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from slowapi.util import get_remote_address

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[settings.rate_limit_default],
    )
    HAS_SLOWAPI = True
except ImportError:
    limiter = NoopLimiter()
    _rate_limit_exceeded_handler = None
    RateLimitExceeded = None
    SlowAPIMiddleware = None
    HAS_SLOWAPI = False
    logger.warning("slowapi not installed; API rate limiting disabled")


# ── Tiered daily AI quota enforcement (in-process counter) ──────────────────
def ai_query_rate(user) -> str:
    """slowapi limit string for the AI query endpoint per tier."""
    if resolve_user_tier(user) == "premium":
        return f"{settings.ai_premium_daily_limit}/day"
    return f"{settings.ai_free_daily_limit}/day"


class _QuotaStore:
    """In-memory daily quota counter: {(user_id, day): count}."""

    def __init__(self) -> None:
        self._counts: Dict[Tuple[str, date], int] = {}
        self._lock = Lock()

    def consume(self, user_id, limit: int) -> None:
        key = (str(user_id), datetime.utcnow().date())
        with self._lock:
            used = self._counts.get(key, 0)
            if used >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        "Daily AI query limit reached "
                        f"({limit}/day). Upgrade to premium for a higher quota."
                    ),
                )
            self._counts[key] = used + 1

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()


_quota_store = _QuotaStore()


def enforce_ai_quota(user) -> None:
    """Raise 429 if the user has exhausted their tier's daily AI quota."""
    limit = (
        settings.ai_premium_daily_limit
        if resolve_user_tier(user) == "premium"
        else settings.ai_free_daily_limit
    )
    _quota_store.consume(user.id, limit)
