"""
WhatsApp Pipeline Rework Step 5 Schema Migration.

Adds lifecycle status, superseded_by tracking, date precision (lowercase),
source raw message linkage, per-message event indexing, revisions audit trail,
and pgvector embedding_vec on PostgreSQL.

Constraints:
- UNIQUE (user_id, source_raw_message_id, event_index) -> uq_event_source
  (In PostgreSQL, NULLs do not collide, so manually created events and legacy rows
  without a source message are unaffected).
- Index ix_events_business_key ON (user_id, course_code, event_type, date_time)

Revision ID: 0007_pipeline_schema
Revises: 0006_raw_message_text_hash
Create Date: 2026-08-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_pipeline_schema"
down_revision = "0006_raw_message_text_hash"
branch_labels = None
depends_on = None

EVENT_STATUS_ENUM_VALUES = ("ACTIVE", "CANCELLED", "SUPERSEDED")
DATE_PRECISION_ENUM_VALUES = ("exact", "day_only", "unknown")


def upgrade():
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Enums / Column definitions
    if is_postgres:
        with op.get_context().autocommit_block():
            op.execute("DO $$ BEGIN CREATE TYPE eventstatus AS ENUM ('ACTIVE', 'CANCELLED', 'SUPERSEDED'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
            op.execute("DO $$ BEGIN CREATE TYPE eventdateprecision AS ENUM ('exact', 'day_only', 'unknown'); EXCEPTION WHEN duplicate_object THEN null; END $$;")

        status_col = sa.Column("status", postgresql.ENUM("ACTIVE", "CANCELLED", "SUPERSEDED", name="eventstatus", create_type=False), nullable=False, server_default="ACTIVE")
        date_precision_col = sa.Column("date_precision", postgresql.ENUM("exact", "day_only", "unknown", name="eventdateprecision", create_type=False), nullable=False, server_default="unknown")
        revisions_col = sa.Column("revisions", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default="[]")
        uuid_type = postgresql.UUID(as_uuid=True)
    else:
        status_col = sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE")
        date_precision_col = sa.Column("date_precision", sa.String(length=20), nullable=False, server_default="unknown")
        revisions_col = sa.Column("revisions", sa.JSON(), nullable=True, server_default="[]")
        uuid_type = sa.String(length=36)

    # Add columns to academic_events
    op.add_column("academic_events", status_col)
    op.add_column("academic_events", sa.Column("superseded_by_id", uuid_type, sa.ForeignKey("academic_events.id", ondelete="SET NULL"), nullable=True))
    op.add_column("academic_events", date_precision_col)
    op.add_column("academic_events", sa.Column("source_raw_message_id", uuid_type, sa.ForeignKey("raw_messages.id", ondelete="SET NULL"), nullable=True))
    op.add_column("academic_events", sa.Column("event_index", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("academic_events", revisions_col)

    # 2. Indexes
    op.create_index(op.f("ix_academic_events_status"), "academic_events", ["status"], unique=False)
    op.create_index(op.f("ix_academic_events_source_raw_message_id"), "academic_events", ["source_raw_message_id"], unique=False)
    op.create_index("ix_events_business_key", "academic_events", ["user_id", "course_code", "event_type", "date_time"], unique=False)

    # 3. Unique constraint: structural duplicate prevention
    op.create_unique_constraint("uq_event_source", "academic_events", ["user_id", "source_raw_message_id", "event_index"])

    # 4. Backfill source_raw_message_id from source_message_id where possible
    try:
        if is_postgres:
            op.execute("""
                UPDATE academic_events ae
                SET source_raw_message_id = rm.id
                FROM raw_messages rm
                WHERE ae.source_message_id = rm.message_id
                  AND ae.source_message_id IS NOT NULL
                  AND ae.source_raw_message_id IS NULL;
            """)
        else:
            op.execute("""
                UPDATE academic_events
                SET source_raw_message_id = (
                    SELECT rm.id FROM raw_messages rm
                    WHERE rm.message_id = academic_events.source_message_id
                    LIMIT 1
                )
                WHERE source_message_id IS NOT NULL
                  AND source_raw_message_id IS NULL;
            """)
    except Exception:
        pass

    # 5. pgvector setup on PostgreSQL
    # TODO(backfill): Run bounded background job to parse JSON string embedding -> embedding_vec
    # and eventually drop legacy string embedding column in a future migration.
    if is_postgres:
        with op.get_context().autocommit_block():
            op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        op.execute("ALTER TABLE academic_events ADD COLUMN IF NOT EXISTS embedding_vec vector(384);")
        op.execute("CREATE INDEX IF NOT EXISTS ix_academic_events_embedding_vec_hnsw ON academic_events USING hnsw (embedding_vec vector_cosine_ops);")


def downgrade():
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("DROP INDEX IF EXISTS ix_academic_events_embedding_vec_hnsw;")
        op.execute("ALTER TABLE academic_events DROP COLUMN IF EXISTS embedding_vec;")

    op.drop_constraint("uq_event_source", "academic_events", type_="unique")
    op.drop_index("ix_events_business_key", table_name="academic_events")
    op.drop_index(op.f("ix_academic_events_source_raw_message_id"), table_name="academic_events")
    op.drop_index(op.f("ix_academic_events_status"), table_name="academic_events")

    op.drop_column("academic_events", "revisions")
    op.drop_column("academic_events", "event_index")
    op.drop_column("academic_events", "source_raw_message_id")
    op.drop_column("academic_events", "date_precision")
    op.drop_column("academic_events", "superseded_by_id")
    op.drop_column("academic_events", "status")
