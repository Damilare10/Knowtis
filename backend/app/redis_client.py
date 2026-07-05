"""
Redis connection helper.

Provides a lightweight, reusable client and a health probe used by the
system status / health endpoints. Connections are created lazily and never
opened at import time, so the application starts even when Redis is offline.
"""
import logging
from typing import Optional, Tuple

from app.config import settings

logger = logging.getLogger(__name__)

try:
    import redis
    HAS_REDIS = True
except ImportError:  # pragma: no cover - redis is a declared dependency
    redis = None
    HAS_REDIS = False
    logger.warning("redis package not installed; Redis health checks disabled")


def get_redis_client():
    # type: () -> Optional[object]
    """Return a Redis client bound to the configured broker URL, or None."""
    if not HAS_REDIS:
        return None
    return redis.from_url(
        settings.redis_url,
        socket_connect_timeout=2,
        socket_timeout=2,
        decode_responses=True,
    )


def check_redis_health() -> Tuple[bool, str]:
    """Ping the Redis broker. Returns (healthy, detail)."""
    if not HAS_REDIS:
        return False, "redis package not installed"
    try:
        client = get_redis_client()
        if client is None:
            return False, "no redis client configured"
        pong = client.ping()
        return bool(pong), "pong" if pong else "no response"
    except Exception as exc:  # noqa: BLE001 - any failure means unhealthy
        logger.debug("Redis health check failed: %s", exc)
        return False, str(exc)
