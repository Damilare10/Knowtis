"""
Add join retry tracking columns to whatsapp_groups.

Prevents the staggered-join scheduler from retrying the same failed group
every 30s indefinitely. Introduces exponential backoff and a hard cap so
persistent failures (e.g. account_reachout_restricted) don't worsen
WhatsApp anti-spam restrictions.

Revision ID: 0003_add_join_retry_tracking
Revises: 0002_add_whatsapp_auth_state
Create Date: 2026-07-08 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_add_join_retry_tracking"
down_revision = "0002_add_whatsapp_auth_state"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("whatsapp_groups", sa.Column("join_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("whatsapp_groups", sa.Column("last_join_attempt", sa.DateTime(), nullable=True))
    op.add_column("whatsapp_groups", sa.Column("next_join_attempt", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("whatsapp_groups", "next_join_attempt")
    op.drop_column("whatsapp_groups", "last_join_attempt")
    op.drop_column("whatsapp_groups", "join_attempts")
