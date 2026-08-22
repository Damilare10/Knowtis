"""
One-shot migration: adds missing columns that were added to the SQLAlchemy
model after the database was already created.

These are safe to run repeatedly — idempotent.
"""
import logging
from sqlalchemy import text, inspect
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


# New members added to ``ProcessingStatus`` after the enum type was first created.
# PostgreSQL materialises SQLEnum as a native type, so the values must be added
# explicitly; SQLite stores it as VARCHAR and needs nothing.
_NEW_PROCESSING_STATUSES = (
    "QUARANTINED",
    "FILTERED_OUT",
    "SKIPPED_EMPTY",
    "SKIPPED_FRAGMENT",
    "SKIPPED_REPEAT",
)


def _migrate_academic_events(engine: Engine, inspector) -> None:
    """Add ``needs_review`` to academic_events.

    The column is read and written by the reply / sliding-window context-recovery
    branch, which previously raised ``AttributeError`` at query build time.
    """
    try:
        columns = {row["name"] for row in inspector.get_columns("academic_events")}
    except Exception as exc:
        logger.warning("Could not inspect table 'academic_events': %s", exc)
        return

    if "needs_review" in columns:
        return

    logger.info("Running startup migration: adding academic_events.needs_review")
    try:
        with engine.connect() as conn:
            if engine.dialect.name == "sqlite":
                conn.execute(text(
                    "ALTER TABLE academic_events ADD COLUMN needs_review BOOLEAN DEFAULT 1 NOT NULL"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_academic_events_needs_review "
                    "ON academic_events (needs_review)"
                ))
            else:
                conn.execute(text(
                    "ALTER TABLE academic_events ADD COLUMN IF NOT EXISTS needs_review "
                    "BOOLEAN DEFAULT TRUE NOT NULL"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_academic_events_needs_review "
                    "ON academic_events (needs_review)"
                ))
            conn.commit()
    except Exception as exc:
        logger.warning("Could not migrate table 'academic_events': %s", exc)


def _migrate_processing_status_enum(engine: Engine) -> None:
    """Add the new ``ProcessingStatus`` members to the PostgreSQL enum type.

    Without this, writing ``QUARANTINED`` or ``FILTERED_OUT`` raises on commit.
    ``ALTER TYPE ... ADD VALUE`` cannot run inside a transaction block on older
    PostgreSQL, so each statement runs with AUTOCOMMIT.
    """
    if engine.dialect.name == "sqlite":
        return  # stored as VARCHAR; nothing to alter

    try:
        with engine.connect() as conn:
            enum_exists = conn.execute(text(
                "SELECT 1 FROM pg_type WHERE typname = 'processingstatus'"
            )).first()
            if not enum_exists:
                return  # table/type not created yet; create_all will build it complete

        autocommit_engine = engine.execution_options(isolation_level="AUTOCOMMIT")
        with autocommit_engine.connect() as conn:
            for value in _NEW_PROCESSING_STATUSES:
                conn.execute(text(
                    f"ALTER TYPE processingstatus ADD VALUE IF NOT EXISTS '{value}'"
                ))
        logger.info("Startup migration: processingstatus enum values verified")
    except Exception as exc:
        logger.warning("Could not extend 'processingstatus' enum: %s", exc)


def run_startup_migrations(engine: Engine) -> None:
    """Add missing columns / enum types to existing tables.

    Call this from the lifespan startup BEFORE any request-handling code
    queries the affected tables.
    """
    inspector = inspect(engine)

    # 0. Pipeline-correctness migrations. These run first because the later
    #    blocks return early, and because the workers depend on them.
    _migrate_academic_events(engine, inspector)
    _migrate_processing_status_enum(engine)

    # 1. Migrate raw_messages table if missing new columns
    try:
        raw_columns = {row["name"] for row in inspector.get_columns("raw_messages")}
        missing_raw = {"quoted_message_id", "quoted_message_text", "ai_attempts"} - raw_columns
        if missing_raw:
            logger.info(
                "Running startup migration: adding raw_messages columns: %s",
                ", ".join(sorted(missing_raw)),
            )
            with engine.connect() as conn:
                for col in missing_raw:
                    if col == "quoted_message_id":
                        conn.execute(text("ALTER TABLE raw_messages ADD COLUMN quoted_message_id VARCHAR(255)"))
                    elif col == "quoted_message_text":
                        conn.execute(text("ALTER TABLE raw_messages ADD COLUMN quoted_message_text TEXT"))
                    elif col == "ai_attempts":
                        if engine.dialect.name == "sqlite":
                            conn.execute(text("ALTER TABLE raw_messages ADD COLUMN ai_attempts INTEGER DEFAULT 0 NOT NULL"))
                            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_raw_messages_ai_attempts ON raw_messages (ai_attempts)"))
                        else:
                            conn.execute(text("ALTER TABLE raw_messages ADD COLUMN IF NOT EXISTS ai_attempts INTEGER DEFAULT 0 NOT NULL"))
                            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_raw_messages_ai_attempts ON raw_messages (ai_attempts)"))
                conn.commit()
    except Exception as exc:
        logger.warning("Could not inspect or migrate table 'raw_messages': %s", exc)

    # 1b. Migrate whatsapp_groups table if missing filter columns
    try:
        group_columns = {row["name"] for row in inspector.get_columns("whatsapp_groups")}
        missing_group_cols = {"monitored_keywords", "monitored_courses", "filter_mode"} - group_columns
        if missing_group_cols:
            logger.info("Running startup migration: adding whatsapp_groups columns: %s", ", ".join(sorted(missing_group_cols)))
            with engine.connect() as conn:
                for col in missing_group_cols:
                    if col == "monitored_keywords":
                        conn.execute(text("ALTER TABLE whatsapp_groups ADD COLUMN monitored_keywords JSON DEFAULT '[]'"))
                    elif col == "monitored_courses":
                        conn.execute(text("ALTER TABLE whatsapp_groups ADD COLUMN monitored_courses JSON DEFAULT '[]'"))
                    elif col == "filter_mode":
                        conn.execute(text("ALTER TABLE whatsapp_groups ADD COLUMN filter_mode VARCHAR(20) DEFAULT 'ALL'"))
                conn.commit()

        # Fix any pending group records that were mistakenly marked as ACTIVE before bot joined, and ensure filter_mode defaults to ALL
        with engine.connect() as conn:
            result = conn.execute(text("UPDATE whatsapp_groups SET coverage_state = 'RECOVERING' WHERE group_jid LIKE 'pending-%' AND coverage_state = 'ACTIVE'"))
            conn.execute(text("UPDATE whatsapp_groups SET filter_mode = 'ALL' WHERE filter_mode IS NULL OR filter_mode = ''"))
            conn.execute(text("""
                DELETE FROM whatsapp_groups 
                WHERE group_jid LIKE 'pending-%' 
                AND is_active = 1
                AND user_id IN (
                    SELECT g1.user_id FROM whatsapp_groups g1 WHERE g1.group_jid NOT LIKE 'pending-%'
                )
            """))
            conn.commit()
            if result.rowcount > 0:
                logger.info("Startup migration: Reset %d pending group(s) mistakenly marked as ACTIVE to RECOVERING", result.rowcount)
    except Exception as exc:
        logger.warning("Could not inspect or migrate table 'whatsapp_groups': %s", exc)

    # 2. Migrate users table if missing columns
    required_user_columns = (
        "role",
        "whatsapp_number",
        "fcm_token",
        "ai_tokens_received",
        "notification_advance_hours",
    )

    try:
        existing_columns = {row["name"] for row in inspector.get_columns("users")}
    except Exception as exc:
        logger.warning("Could not inspect columns, table 'users' may not exist yet: %s", exc)
        return

    missing_columns = set(required_user_columns) - existing_columns

    if not missing_columns:
        return

    logger.info(
        "Running startup migration: adding missing users columns: %s",
        ", ".join(sorted(missing_columns)),
    )

    with engine.connect() as conn:
        if engine.dialect.name == "sqlite":
            for col in missing_columns:
                if col == "role":
                    conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'student' NOT NULL"))
                elif col == "whatsapp_number":
                    conn.execute(text("ALTER TABLE users ADD COLUMN whatsapp_number VARCHAR(50)"))
                    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_whatsapp_number ON users (whatsapp_number)"))
                elif col == "fcm_token":
                    conn.execute(text("ALTER TABLE users ADD COLUMN fcm_token VARCHAR(255)"))
                elif col == "ai_tokens_received":
                    conn.execute(text("ALTER TABLE users ADD COLUMN ai_tokens_received INTEGER DEFAULT 0 NOT NULL"))
                elif col == "notification_advance_hours":
                    conn.execute(text("ALTER TABLE users ADD COLUMN notification_advance_hours INTEGER DEFAULT 3 NOT NULL"))
        else:
            # PostgreSQL migration
            # We construct a dynamic migration SQL only for the missing columns to be safe
            migration_parts = []
            if "role" in missing_columns:
                migration_parts.append("""
DO $$ BEGIN
    CREATE TYPE sgeum AS ENUM ('student', 'admin');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;
ALTER TABLE users ADD COLUMN IF NOT EXISTS role sgeum DEFAULT 'student' NOT NULL;
""")
            if "whatsapp_number" in missing_columns:
                migration_parts.append("""
ALTER TABLE users ADD COLUMN IF NOT EXISTS whatsapp_number VARCHAR(50);
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_users_whatsapp_number'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT uq_users_whatsapp_number UNIQUE (whatsapp_number);
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_users_whatsapp_number ON users (whatsapp_number);
""")
            if "fcm_token" in missing_columns:
                migration_parts.append("ALTER TABLE users ADD COLUMN IF NOT EXISTS fcm_token VARCHAR(255);")
            if "ai_tokens_received" in missing_columns:
                migration_parts.append("ALTER TABLE users ADD COLUMN IF NOT EXISTS ai_tokens_received INTEGER DEFAULT 0 NOT NULL;")
            if "notification_advance_hours" in missing_columns:
                migration_parts.append("ALTER TABLE users ADD COLUMN IF NOT EXISTS notification_advance_hours INTEGER DEFAULT 3 NOT NULL;")
            
            if migration_parts:
                conn.execute(text("\n".join(migration_parts)))

        conn.commit()

