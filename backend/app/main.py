"""
Main FastAPI Application Entrypoint
"""
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.logging_config import setup_logging
from app.routes import auth_routes
from app.routes import events_routes
from app.routes import reminders_routes
from app.routes import whatsapp_routes
from app.routes import notifications_routes
from app.routes import calendar_routes
from app.routes import billing_routes
from app.routes import ocr_routes
from app.routes import ai_routes
from app.routes import realtime_routes
from app.routes import widget_routes
from app.routes import training_routes
from app.routes import onboarding_routes
from app.rate_limit import (
    HAS_SLOWAPI,
    RateLimitExceeded,
    SlowAPIMiddleware,
    _rate_limit_exceeded_handler,
    limiter,
)


logger = logging.getLogger(__name__)
# Structured logger for per-request access/error lines. Configured lazily by
# setup_logging(); the lazy proxy picks up configuration on first use.
access_log = structlog.get_logger("knowtis.access")


# ── Application lifespan ──────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic"""
    # Configure structured logging first so every subsequent line is structured.
    setup_logging(
        level=settings.log_level,
        log_format=settings.log_format,
        debug=settings.debug,
    )
    logger.info(
        "Structured logging initialized",
        extra={"log_format": settings.log_format, "level": settings.log_level},
    )

    # Create DB tables
    from app.database import engine, Base
    from app import models  # noqa — ensures all models are registered
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified/created")

    if settings.semantic_prewarm_enabled:
        # Pre-warm the semantic event-type classifier so the first WhatsApp
        # message does not pay the MiniLM embedding cost on the critical path.
        try:
            from app.services.semantic_classifier import prewarm
            prewarm()
        except Exception as exc:
            logger.warning("Semantic classifier prewarm failed: %s", exc)
    else:
        logger.info("Semantic classifier prewarm disabled")

    # Start background scheduler
    from app.scheduler import start_scheduler
    start_scheduler()

    yield  # Application runs here

    # Shutdown scheduler
    from app.scheduler import stop_scheduler
    stop_scheduler()
    logger.info("Application shutdown complete")


# ── OpenAPI metadata ──────────────────────────────────────────────────────────
def _build_openapi_servers() -> list:
    """Build the OpenAPI `servers` list from env, falling back to BACKEND_URL."""
    raw = (settings.openapi_servers or "").strip()
    if raw:
        return [{"url": url.strip()} for url in raw.split(",") if url.strip()]
    return [{"url": settings.backend_url, "description": "Default server"}]


openapi_tags = [
    {"name": "System", "description": "Health checks and service status endpoints."},
    {"name": "Authentication", "description": "Google OAuth and email/password authentication, plus JWT issuance and refresh."},
    {"name": "Academic Events", "description": "Extraction, classification, semantic search and deduplication of academic events."},
    {"name": "Reminders", "description": "Countdown and priority-based reminder generation."},
    {"name": "WhatsApp", "description": "WhatsApp group ingestion webhooks and connector integration."},
    {"name": "Notifications", "description": "Night briefs and the in-app notification inbox."},
    {"name": "OCR", "description": "On-demand image OCR and structured schedule extraction."},
    {"name": "Calendar", "description": "Google Calendar / Outlook one-click synchronization."},
    {"name": "Billing", "description": "RevenueCat webhooks and premium subscription sync."},
    {"name": "AI", "description": "AI Catch-Up Agent — deterministic (free) and Groq-powered conversational (premium) query engine."},
    {"name": "Realtime", "description": "WebSocket and SSE live feed for dashboard events, reminders and notifications."},
    {"name": "Widgets", "description": "Supplies data formatted for the homescreen widgets."},
]


# ── Request-id middleware ─────────────────────────────────────────────────────
def _extract_user_id(request: Request) -> Optional[str]:
    """Best-effort extraction of the authenticated user id (JWT ``sub``) for logging."""
    token = request.query_params.get("token")
    auth_header = request.headers.get("Authorization", "")
    if not token and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
    if not token:
        return None
    try:
        from app.services.auth_service import AuthService
        payload = AuthService._decode_token(token, settings.jwt_secret_key)
        if payload and payload.get("type") == "access":
            return payload.get("sub")
    except Exception:
        pass
    return None


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generate/propagate an ``X-Request-ID`` header and bind request-scoped log context.

    Reads an incoming ``X-Request-ID`` or generates a uuid4, attaches it to the
    response header, and binds ``request_id`` / ``user_id`` / ``route`` / ``method``
    to the structlog contextvar so every log line emitted during the request
    (from any logger) carries them.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            user_id=_extract_user_id(request),
            route=request.url.path,
            method=request.method,
        )

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Unhandled errors are turned into a 500 by the global exception
            # handler, which sits above this middleware. Log the failed request
            # and re-raise so the handler still runs; the response header is
            # set there.
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            access_log.error("request_failed", status_code=500, duration_ms=duration_ms)
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        response.headers["X-Request-ID"] = request_id
        access_log.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Knowtis API",
    description=(
        "AI-powered academic communication assistant. "
        "Extracts, classifies, and delivers actionable academic updates from WhatsApp groups."
    ),
    version="0.2.0",
    openapi_tags=openapi_tags,
    servers=_build_openapi_servers(),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Rate limiter state
if HAS_SLOWAPI:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request-id + structured access logging (added last so it wraps all other middleware)
app.add_middleware(RequestIDMiddleware)


# ── Error handling ─────────────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled errors: log with request_id and return a uniform 500.

    Tracebacks are never returned to clients in production (gated by ``DEBUG``);
    they are always logged server-side for debugging.
    """
    request_id = getattr(request.state, "request_id", None)
    access_log.bind(
        request_id=request_id,
        route=request.url.path,
        method=request.method,
    ).exception("unhandled_exception", error_type=type(exc).__name__)

    body: dict = {"detail": "Internal server error", "request_id": request_id}
    if settings.debug:
        import traceback as _tb
        body["traceback"] = "".join(_tb.format_exception(type(exc), exc, exc.__traceback__))
    response = JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=body)
    response.headers["X-Request-ID"] = request_id or ""
    return response


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_routes.router)
app.include_router(events_routes.router)
app.include_router(reminders_routes.router)
app.include_router(whatsapp_routes.router)
app.include_router(notifications_routes.router)
app.include_router(calendar_routes.router)
app.include_router(billing_routes.router)
app.include_router(ocr_routes.router)
app.include_router(ai_routes.router)
app.include_router(realtime_routes.router)
app.include_router(widget_routes.router)
app.include_router(training_routes.router)
app.include_router(onboarding_routes.router)


# ── Health & status ───────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/health/redis", tags=["System"])
async def redis_health_check():
    """Redis broker health check — pings the configured Celery broker."""
    from app.redis_client import check_redis_health
    from app.config import settings

    healthy, detail = check_redis_health()
    return {
        "status": "healthy" if healthy else "unhealthy",
        "broker_url": settings.celery_broker_url,
        "detail": detail,
    }


@app.get("/status", tags=["System"])
async def system_status():
    """System status with component availability"""
    from app.services.ocr_service import HAS_TESSERACT, HAS_PADDLE, HAS_CV2
    from app.scheduler import _scheduler, HAS_APSCHEDULER
    from app.redis_client import HAS_REDIS, check_redis_health

    redis_healthy, redis_detail = check_redis_health() if HAS_REDIS else (False, "redis not installed")

    return {
        "status": "online",
        "version": "0.2.0",
        "service": "Knowtis Backend Service",
        "components": {
            "database": "connected",
            "rate_limiting": "enabled" if HAS_SLOWAPI else "disabled (install slowapi)",
            "scheduler": "running" if (HAS_APSCHEDULER and _scheduler and _scheduler.running) else "disabled",
            "redis": "connected" if redis_healthy else f"unavailable ({redis_detail})",
            "ocr_paddle": "available" if HAS_PADDLE else "unavailable (install paddleocr)",
            "ocr_tesseract": "available" if HAS_TESSERACT else "unavailable (install pytesseract)",
            "ocr_preprocessing": "available" if HAS_CV2 else "unavailable (install opencv-python-headless)",
        },
    }
