"""
Configuration settings for Knowtis
Loads from environment variables with sensible defaults for development.
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()



def _get_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _get_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


def _is_insecure_secret(value: str, default: str) -> bool:
    return not value or value == default or "CHANGE_ME" in value


class Settings:
    """Application settings loaded from environment variables."""

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./knowtis.db")

    # ── JWT / Auth ────────────────────────────────────────────────────────────
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "SUPER_SECRET_JWT_KEY_CHANGE_ME")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    refresh_token_secret: str = os.getenv("REFRESH_TOKEN_SECRET", "SUPER_SECRET_REFRESH_KEY_CHANGE_ME")
    refresh_token_expire_days: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))

    # ── Google OAuth ──────────────────────────────────────────────────────────
    google_client_id: Optional[str] = os.getenv("GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = os.getenv("GOOGLE_CLIENT_SECRET")
    backend_url: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # ── Microsoft OAuth (Outlook calendar) ───────────────────────────────────
    outlook_client_id: Optional[str] = os.getenv("OUTLOOK_CLIENT_ID")
    outlook_client_secret: Optional[str] = os.getenv("OUTLOOK_CLIENT_SECRET")

    # ── RevenueCat ────────────────────────────────────────────────────────────
    revenuecat_webhook_secret: Optional[str] = os.getenv("REVENUECAT_WEBHOOK_SECRET")

    # ── AI / Embeddings ───────────────────────────────────────────────────────
    similarity_threshold: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.75"))
    setfit_classifier_enabled: bool = _get_bool("SETFIT_CLASSIFIER_ENABLED", True)
    setfit_classifier_path: str = os.getenv(
        "SETFIT_CLASSIFIER_PATH",
        os.path.join(os.path.dirname(__file__), "models", "setfit_classifier"),
    )
    setfit_min_confidence: float = _get_float("SETFIT_MIN_CONFIDENCE", 0.45)

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    rate_limit_default: str = os.getenv("RATE_LIMIT_DEFAULT", "100/minute")
    rate_limit_auth: str = os.getenv("RATE_LIMIT_AUTH", "10/minute")
    rate_limit_ocr_free: str = os.getenv("RATE_LIMIT_OCR_FREE", "10/hour")
    rate_limit_ocr_premium: str = os.getenv("RATE_LIMIT_OCR_PREMIUM", "50/hour")

    # ── WhatsApp Connector ────────────────────────────────────────────────────
    whatsapp_connector_url: str = os.getenv("WHATSAPP_CONNECTOR_URL", "http://localhost:3001")
    whatsapp_connector_timeout: float = float(os.getenv("WHATSAPP_CONNECTOR_TIMEOUT", "30.0"))
    # Shared secret expected in the ``X-Webhook-Secret`` header on
    # ``/api/v1/whatsapp/webhook``. When empty, the webhook is rejected
    # fail-closed.
    whatsapp_connector_webhook_secret: str = os.getenv(
        "WHATSAPP_CONNECTOR_WEBHOOK_SECRET", ""
    )
    whatsapp_connector_api_secret: str = os.getenv(
        "WHATSAPP_CONNECTOR_API_SECRET",
        os.getenv("WHATSAPP_CONNECTOR_WEBHOOK_SECRET", ""),
    )

    # ── AI Catch-Up Agent (Groq LLM layer) ─────────────────────────────────────
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_base_url: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    ai_free_model: str = os.getenv("AI_FREE_MODEL", "llama-3.1-8b-instant")
    ai_premium_model: str = os.getenv("AI_PREMIUM_MODEL", "llama-3.3-70b-versatile")
    ai_request_timeout: float = float(os.getenv("AI_REQUEST_TIMEOUT", "60"))
    ai_temperature: float = float(os.getenv("AI_TEMPERATURE", "0.4"))
    ai_max_tokens: int = int(os.getenv("AI_MAX_TOKENS", "1024"))
    ai_free_daily_limit: int = int(os.getenv("AI_FREE_DAILY_LIMIT", "20"))
    ai_premium_daily_limit: int = int(os.getenv("AI_PREMIUM_DAILY_LIMIT", "200"))

    # ── Premium Real-Time Alerts (push/DM channel) ────────────────────────────
    push_webhook_url: str = os.getenv("PUSH_WEBHOOK_URL", "")
    push_webhook_enabled: bool = _get_bool("PUSH_WEBHOOK_ENABLED", False)
    push_webhook_timeout_seconds: float = _get_float("PUSH_WEBHOOK_TIMEOUT_SECONDS", 5.0)
    timeline_shift_threshold_minutes: float = _get_float("TIMELINE_SHIFT_THRESHOLD_MINUTES", 5.0)

    # ── Celery & Redis ────────────────────────────────────────────────────────
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    # Production runs a real Celery worker (False). Tests force True via conftest.
    celery_task_always_eager: bool = os.getenv("CELERY_TASK_ALWAYS_EAGER", "False").lower() in ("true", "1", "yes")

    # ── Worker Burst Protection (randomized jitter injected before task bodies) ─
    worker_jitter_min_seconds: float = float(os.getenv("WORKER_JITTER_MIN_SECONDS", "0.5"))
    worker_jitter_max_seconds: float = float(os.getenv("WORKER_JITTER_MAX_SECONDS", "2.0"))

    # ── WhatsApp Anti-Ban Session Rotation ─────────────────────────────────────
    whatsapp_session_rotation_interval_minutes: int = int(os.getenv("WHATSAPP_SESSION_ROTATION_INTERVAL_MINUTES", "120"))
    whatsapp_worker_pool_size: int = int(os.getenv("WHATSAPP_WORKER_POOL_SIZE", "3"))

    # ── WhatsApp Headless Listener ─────────────────────────────────────────────
    # Polling cadence and exponential-backoff ceiling for the listener cycle.
    whatsapp_listener_enabled: bool = _get_bool("WHATSAPP_LISTENER_ENABLED", True)
    whatsapp_listener_poll_interval: float = _get_float("WHATSAPP_LISTENER_POLL_INTERVAL", 60.0)
    whatsapp_listener_max_backoff: float = _get_float("WHATSAPP_LISTENER_MAX_BACKOFF", 900.0)
    recovery_backfill_limit: int = int(os.getenv("RECOVERY_BACKFILL_LIMIT", "100"))
    recovery_enabled: bool = _get_bool("RECOVERY_ENABLED", True)

    # ── Firebase Cloud Messaging ──────────────────────────────────────────────
    firebase_credentials_json: Optional[str] = os.getenv("FIREBASE_CREDENTIALS_JSON")

    # ── Logging & Observability ───────────────────────────────────────────────
    app_env: str = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).lower()
    debug: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
    scheduler_enabled: bool = _get_bool(
        "SCHEDULER_ENABLED",
        os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).lower() in {"production", "prod"},
    )
    semantic_prewarm_enabled: bool = _get_bool(
        "SEMANTIC_PREWARM_ENABLED",
        os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).lower() in {"production", "prod"},
    )
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_format: str = os.getenv("LOG_FORMAT", "json")  # "json" | "console"
    # Comma-separated server URLs surfaced in the OpenAPI spec (empty -> BACKEND_URL)
    openapi_servers: str = os.getenv("OPENAPI_SERVERS", "")

    # ── Timezone ──────────────────────────────────────────────────────────────
    # IANA zone name used for wall-clock display and relative-date parsing
    # (e.g. "tomorrow", "Friday at 2pm"). Africa/Lagos = UTC+1, no DST.
    app_timezone: str = os.getenv("APP_TIMEZONE", "Africa/Lagos")

    def llm_enabled(self) -> bool:
        return bool(self.groq_api_key)

    def firebase_enabled(self) -> bool:
        return bool(self.firebase_credentials_json)

    def __init__(self):
        # Re-read values to allow runtime override in tests
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./knowtis.db")
        self.jwt_secret_key = os.getenv("JWT_SECRET_KEY", "SUPER_SECRET_JWT_KEY_CHANGE_ME")
        self.jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
        self.refresh_token_secret = os.getenv("REFRESH_TOKEN_SECRET", "SUPER_SECRET_REFRESH_KEY_CHANGE_ME")
        self.refresh_token_expire_days = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        self.outlook_client_id = os.getenv("OUTLOOK_CLIENT_ID")
        self.outlook_client_secret = os.getenv("OUTLOOK_CLIENT_SECRET")
        self.revenuecat_webhook_secret = os.getenv("REVENUECAT_WEBHOOK_SECRET")
        self.similarity_threshold = float(os.getenv("SIMILARITY_THRESHOLD", "0.75"))
        self.setfit_classifier_enabled = _get_bool("SETFIT_CLASSIFIER_ENABLED", True)
        self.setfit_classifier_path = os.getenv(
            "SETFIT_CLASSIFIER_PATH",
            os.path.join(os.path.dirname(__file__), "models", "setfit_classifier"),
        )
        self.setfit_min_confidence = _get_float("SETFIT_MIN_CONFIDENCE", 0.45)
        self.rate_limit_default = os.getenv("RATE_LIMIT_DEFAULT", "100/minute")
        self.rate_limit_auth = os.getenv("RATE_LIMIT_AUTH", "10/minute")
        self.rate_limit_ocr_free = os.getenv("RATE_LIMIT_OCR_FREE", "10/hour")
        self.rate_limit_ocr_premium = os.getenv("RATE_LIMIT_OCR_PREMIUM", "50/hour")
        self.whatsapp_connector_url = os.getenv("WHATSAPP_CONNECTOR_URL", "http://localhost:3001")
        self.whatsapp_connector_timeout = float(os.getenv("WHATSAPP_CONNECTOR_TIMEOUT", "30.0"))
        self.whatsapp_connector_webhook_secret = os.getenv(
            "WHATSAPP_CONNECTOR_WEBHOOK_SECRET", ""
        )
        self.whatsapp_connector_api_secret = os.getenv(
            "WHATSAPP_CONNECTOR_API_SECRET",
            self.whatsapp_connector_webhook_secret,
        )
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.groq_base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
        self.ai_free_model = os.getenv("AI_FREE_MODEL", "llama-3.1-8b-instant")
        self.ai_premium_model = os.getenv("AI_PREMIUM_MODEL", "llama-3.3-70b-versatile")
        self.ai_request_timeout = float(os.getenv("AI_REQUEST_TIMEOUT", "60"))
        self.ai_temperature = float(os.getenv("AI_TEMPERATURE", "0.4"))
        self.ai_max_tokens = int(os.getenv("AI_MAX_TOKENS", "1024"))
        self.ai_free_daily_limit = int(os.getenv("AI_FREE_DAILY_LIMIT", "20"))
        self.ai_premium_daily_limit = int(os.getenv("AI_PREMIUM_DAILY_LIMIT", "200"))
        self.push_webhook_url = os.getenv("PUSH_WEBHOOK_URL", "")
        self.push_webhook_enabled = _get_bool("PUSH_WEBHOOK_ENABLED", False)
        self.push_webhook_timeout_seconds = _get_float("PUSH_WEBHOOK_TIMEOUT_SECONDS", 5.0)
        self.timeline_shift_threshold_minutes = _get_float("TIMELINE_SHIFT_THRESHOLD_MINUTES", 5.0)
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.celery_broker_url = os.getenv("CELERY_BROKER_URL", self.redis_url)
        self.celery_result_backend = os.getenv("CELERY_RESULT_BACKEND", self.redis_url)
        self.celery_task_always_eager = os.getenv("CELERY_TASK_ALWAYS_EAGER", "False").lower() in ("true", "1", "yes")
        self.worker_jitter_min_seconds = float(os.getenv("WORKER_JITTER_MIN_SECONDS", "0.5"))
        self.worker_jitter_max_seconds = float(os.getenv("WORKER_JITTER_MAX_SECONDS", "2.0"))
        self.whatsapp_session_rotation_interval_minutes = int(os.getenv("WHATSAPP_SESSION_ROTATION_INTERVAL_MINUTES", "120"))
        self.whatsapp_worker_pool_size = int(os.getenv("WHATSAPP_WORKER_POOL_SIZE", "3"))
        self.whatsapp_listener_enabled = _get_bool("WHATSAPP_LISTENER_ENABLED", True)
        self.whatsapp_listener_poll_interval = _get_float("WHATSAPP_LISTENER_POLL_INTERVAL", 60.0)
        self.whatsapp_listener_max_backoff = _get_float("WHATSAPP_LISTENER_MAX_BACKOFF", 900.0)
        self.recovery_backfill_limit = int(os.getenv("RECOVERY_BACKFILL_LIMIT", "100"))
        self.recovery_enabled = _get_bool("RECOVERY_ENABLED", True)
        self.firebase_credentials_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
        self.app_env = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).lower()
        self.debug = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
        self.scheduler_enabled = _get_bool("SCHEDULER_ENABLED", self.app_env in {"production", "prod"})
        self.semantic_prewarm_enabled = _get_bool("SEMANTIC_PREWARM_ENABLED", self.app_env in {"production", "prod"})
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.log_format = os.getenv("LOG_FORMAT", "json")
        self.openapi_servers = os.getenv("OPENAPI_SERVERS", "")
        self.app_timezone = os.getenv("APP_TIMEZONE", "Africa/Lagos")

        if self.app_env in {"production", "prod"}:
            if _is_insecure_secret(self.jwt_secret_key, "SUPER_SECRET_JWT_KEY_CHANGE_ME"):
                raise RuntimeError("JWT_SECRET_KEY must be set to a strong non-default value in production.")
            if _is_insecure_secret(self.refresh_token_secret, "SUPER_SECRET_REFRESH_KEY_CHANGE_ME"):
                raise RuntimeError("REFRESH_TOKEN_SECRET must be set to a strong non-default value in production.")


settings = Settings()
