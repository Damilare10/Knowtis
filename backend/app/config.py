"""
Configuration settings for Knowtis
"""
import os
from pydantic import BaseModel

class Settings(BaseModel):
    # Base configuration
    similarity_threshold: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.75"))
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./knowtis.db")
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "SUPER_SECRET_JWT_KEY_CHANGE_ME")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    app_timezone: str = os.getenv("APP_TIMEZONE", "Africa/Lagos")
    backend_url: str = os.getenv("BACKEND_URL", "http://localhost:8000")

    # Redis & Celery
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    celery_task_always_eager: bool = os.getenv("CELERY_TASK_ALWAYS_EAGER", "False").lower() in ("true", "1", "yes")

    # Worker Jitter
    worker_jitter_min_seconds: float = float(os.getenv("WORKER_JITTER_MIN_SECONDS", "0.5"))
    worker_jitter_max_seconds: float = float(os.getenv("WORKER_JITTER_MAX_SECONDS", "2.0"))

    # WhatsApp Connector config
    whatsapp_connector_url: str = os.getenv("WHATSAPP_CONNECTOR_URL", "http://localhost:3001")
    whatsapp_connector_timeout: float = float(os.getenv("WHATSAPP_CONNECTOR_TIMEOUT", "30.0"))
    whatsapp_connector_webhook_secret: str = os.getenv("WHATSAPP_CONNECTOR_WEBHOOK_SECRET", "")
    
    # WhatsApp Listener config
    whatsapp_listener_enabled: bool = os.getenv("WHATSAPP_LISTENER_ENABLED", "True").lower() in ("true", "1", "yes")
    whatsapp_listener_poll_interval: float = float(os.getenv("WHATSAPP_LISTENER_POLL_INTERVAL", "10.0"))
    whatsapp_listener_max_backoff: float = float(os.getenv("WHATSAPP_LISTENER_MAX_BACKOFF", "300.0"))
    whatsapp_session_rotation_interval_minutes: int = int(os.getenv("WHATSAPP_SESSION_ROTATION_INTERVAL_MINUTES", "120"))
    whatsapp_worker_pool_size: int = int(os.getenv("WHATSAPP_WORKER_POOL_SIZE", "3"))

    # Recovery Config
    recovery_enabled: bool = os.getenv("RECOVERY_ENABLED", "True").lower() in ("true", "1", "yes")
    recovery_backfill_limit: int = int(os.getenv("RECOVERY_BACKFILL_LIMIT", "100"))

    # OAuth & External APIs
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    outlook_client_id: str = os.getenv("OUTLOOK_CLIENT_ID", "")
    outlook_client_secret: str = os.getenv("OUTLOOK_CLIENT_SECRET", "")
    revenuecat_webhook_secret: str = os.getenv("REVENUECAT_WEBHOOK_SECRET", "")

    # AI Catch-up Agent / LLM Settings
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_base_url: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    ai_premium_model: str = os.getenv("AI_PREMIUM_MODEL", "llama-3.3-70b-versatile")
    ai_temperature: float = float(os.getenv("AI_TEMPERATURE", "0.4"))
    ai_max_tokens: int = int(os.getenv("AI_MAX_TOKENS", "1024"))
    ai_request_timeout: float = float(os.getenv("AI_REQUEST_TIMEOUT", "60.0"))
    ai_free_daily_limit: int = int(os.getenv("AI_FREE_DAILY_LIMIT", "20"))
    ai_premium_daily_limit: int = int(os.getenv("AI_PREMIUM_DAILY_LIMIT", "200"))

    # Rate Limiting
    rate_limit_default: str = os.getenv("RATE_LIMIT_DEFAULT", "100/minute")

    @property
    def llm_enabled(self) -> bool:
        return bool(self.groq_api_key)

settings = Settings()
