"""
Add text_hash column to raw_messages for deterministic prefiltering.

Revision ID: 0006_raw_message_text_hash
Revises: 0005_raw_message_ai_attempts
Create Date: 2026-08-22 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_raw_message_text_hash"
down_revision = "0005_raw_message_ai_attempts"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("raw_messages", sa.Column("text_hash", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_raw_messages_text_hash"), "raw_messages", ["text_hash"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_raw_messages_text_hash"), table_name="raw_messages")
    op.drop_column("raw_messages", "text_hash")
