"""
One-shot migration: adds missing columns that were added to the SQLAlchemy
model after the database was already created.

These are safe to run repeatedly — idempotent.
"""
import logging
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def run_startup_migrations(engine: Engine) -> None:
    """Add missing columns / enum types to existing tables.

    Call this from the lifespan startup BEFORE any request-handling code
    queries the affected tables.
    """
    required_user_columns = (
        "role",
        "whatsapp_number",
        "fcm_token",
        "ai_tokens_received",
    )

    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT column_name "
                "FROM information_schema.columns "
                "WHERE table_name = 'users' "
                "AND column_name = ANY(:column_names)"
            ),
            {"column_names": list(required_user_columns)},
        )
        existing_columns = {row.column_name for row in result}
        missing_columns = set(required_user_columns) - existing_columns
        needs_migration = bool(missing_columns)

        if needs_migration:
            logger.info(
                "Running startup migration: adding missing users columns: %s",
                ", ".join(sorted(missing_columns)),
            )
            conn.execute(text(_MIGRATION_SQL))

        conn.commit()


# ── Migration SQL ─────────────────────────────────────────────────────────────
_MIGRATION_SQL = """
-- ── users.role (UserRole enum + column) ──────────────────────────────────────
DO $$ BEGIN
    CREATE TYPE sgeum AS ENUM ('student', 'admin');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

ALTER TABLE users ADD COLUMN IF NOT EXISTS role sgeum DEFAULT 'student' NOT NULL;

-- ── users.whatsapp_number ────────────────────────────────────────────────────
ALTER TABLE users ADD COLUMN IF NOT EXISTS whatsapp_number VARCHAR(50);
-- Only add unique constraint if it doesn't already exist
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_users_whatsapp_number'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT uq_users_whatsapp_number UNIQUE (whatsapp_number);
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_users_whatsapp_number ON users (whatsapp_number);

-- ── users.fcm_token ──────────────────────────────────────────────────────────
ALTER TABLE users ADD COLUMN IF NOT EXISTS fcm_token VARCHAR(255);

-- ── users.ai_tokens_received ────────────────────────────────────────────────
ALTER TABLE users ADD COLUMN IF NOT EXISTS ai_tokens_received INTEGER DEFAULT 0 NOT NULL;
"""
