"""
Shared rate limiting setup.
Routes can safely import ``limiter`` even when slowapi is not installed.
"""
import logging
from datetime import datetime, date
from threading import Lock
from typing import Dict, Tuple, Optional

from fastapi import HTTPException, status, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

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


class RateLimitLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log rate limit events to the database."""

    def __init__(self, app, db_session_factory=None):
        super().__init__(app)
        self.db_session_factory = db_session_factory

    async def dispatch(self, request: Request, call_next):
        # Process request first
        response = await call_next(request)

        # Check if rate limited (429 status)
        if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            # Log to database if we have a session factory
            if self.db_session_factory:
                try:
                    self._log_rate_limit_event(request, response)
                except Exception as e:
                    logger.warning(f"Failed to log rate limit event: {e}")

        return response

    def _log_rate_limit_event(self, request: Request, response: Response):
        """Log rate limit event to database."""
        from app.models import RateLimitLog, User
        from app.services.auth_service import AuthService

        db = self.db_session_factory()
        try:
            # Try to get user from token
            user_id = None
            user_tier = None
            auth_header = request.headers.get("Authorization", "")
            token = None
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ", 1)[1]
            elif "token" in request.query_params:
                token = request.query_params["token"]

            if token:
                try:
                    user = AuthService.get_user_from_token(token, db)
                    if user:
                        user_id = user.id
                        user_tier = resolve_user_tier(user)
                except Exception:
                    pass

            # Get IP
            ip = request.client.host if request.client else None
            # Check for forwarded IP
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                ip = forwarded.split(",")[0].strip()

            # Get limit info from response headers
            limit_rule = response.headers.get("X-RateLimit-Limit", "unknown")
            current_count = response.headers.get("X-RateLimit-Remaining", "0")

            log = RateLimitLog(
                user_id=user_id,
                ip_address=ip,
                endpoint=str(request.url.path),
                method=request.method,
                limit_key=f"{request.method}:{request.url.path}:{ip}",
                limit_rule=limit_rule,
                current_count=int(current_count) if current_count.isdigit() else 0,
                limit_max=int(limit_rule.split("/")[0]) if "/" in limit_rule and limit_rule.split("/")[0].isdigit() else 0,
                blocked=True,
                user_tier=user_tier,
                user_agent=request.headers.get("User-Agent")
            )
            db.add(log)
            db.commit()
        finally:
            db.close()


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
