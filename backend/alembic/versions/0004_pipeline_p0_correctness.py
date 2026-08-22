"""
P0 pipeline correctness: academic_events.needs_review + ProcessingStatus members.

Two writes in the message pipeline referenced schema that did not exist:

* ``AcademicEvent.needs_review`` was read and written by the reply /
  sliding-window context-recovery branch, but the column only existed on
  ``prediction_records``. The query filter raised ``AttributeError`` at build
  time, so the whole branch was dead code.
* ``ProcessingStatus`` only declared PENDING/PROCESSED/FAILED while the workers
  wrote ``QUARANTINED`` (submission gate) and ``FILTERED_OUT`` (group
  ``filter_mode == "FILTERED"``), which raised on commit.

Revision ID: 0004_pipeline_p0_correctness
Revises: 0003_add_join_retry_tracking
Create Date: 2026-08-21 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_pipeline_p0_correctness"
down_revision = "0003_add_join_retry_tracking"
branch_labels = None
depends_on = None


NEW_PROCESSING_STATUSES = (
    "QUARANTINED",
    "FILTERED_OUT",
    "SKIPPED_EMPTY",
    "SKIPPED_FRAGMENT",
    "SKIPPED_REPEAT",
)


def upgrade():
    op.add_column(
        "academic_events",
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(
        "ix_academic_events_needs_review", "academic_events", ["needs_review"]
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # ALTER TYPE ... ADD VALUE cannot run inside a transaction block on
        # PostgreSQL < 12, so escape the migration transaction explicitly.
        with op.get_context().autocommit_block():
            for value in NEW_PROCESSING_STATUSES:
                op.execute(
                    f"ALTER TYPE processingstatus ADD VALUE IF NOT EXISTS '{value}'"
                )


def downgrade():
    op.drop_index("ix_academic_events_needs_review", table_name="academic_events")
    op.drop_column("academic_events", "needs_review")
    # PostgreSQL cannot remove a value from an enum type; the extra members are
    # left in place, which is harmless because nothing writes them after the
    # column-level rollback.
