"""
Add ai_attempts to raw_messages.

Enables batch bisect and poison message quarantine on repeated extraction failures.

Revision ID: 0005_raw_message_ai_attempts
Revises: 0004_pipeline_p0_correctness
Create Date: 2026-08-21 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_raw_message_ai_attempts"
down_revision = "0004_pipeline_p0_correctness"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "raw_messages",
        sa.Column("ai_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_raw_messages_ai_attempts", "raw_messages", ["ai_attempts"]
    )


def downgrade():
    op.drop_index("ix_raw_messages_ai_attempts", table_name="raw_messages")
    op.drop_column("raw_messages", "ai_attempts")
