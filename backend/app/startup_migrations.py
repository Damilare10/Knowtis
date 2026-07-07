"""
One-shot migration: adds missing columns that were added to the SQLAlchemy
model after the database was already created.

These are safe to run repeatedly — they use IF NOT EXISTS so they are
idempotent.
"""
import logging
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Ordered list of (sql_statements) — each block is run atomically inside
# the single transaction started by run_startup_migrations.
MIGRATION_SQL = """
-- ── users.role (UserRole enum + column) ──────────────────────────────────────
DO $$ BEGIN
    CREATE TYPE sgeum AS ENUM ('student', 'admin');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

ALTER TABLE users ADD COLUMN role sgeum DEFAULT 'student' NOT NULL;
"""


def run_startup_migrations(engine: Engine) -> None:
    """Add missing columns / enum types to existing tables.

    Call this from the lifespan startup BEFORE any request-handling code
    queries the affected tables.
    """
    with engine.connect() as conn:
        # Log which statements actually executed (adds the column or skips)
        result = conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT FROM information_schema.columns "
                "  WHERE table_name = 'users' AND column_name = 'role'"
                ")"
            )
        )
        exists = result.scalar_one()

        if exists:
            logger.info("Column users.role already exists, skipping migration")
        else:
            logger.info("Running startup migration: adding users.role column")
            conn.execute(text(MIGRATION_SQL))

        conn.commit()
