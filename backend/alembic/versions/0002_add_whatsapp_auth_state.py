"""
Add whatsapp_auth_state table for Baileys auth persistence on Render free tier.

Revision ID: 0002_add_whatsapp_auth_state
Revises: 0001_add_user_role
Create Date: 2026-07-08 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_add_whatsapp_auth_state"
down_revision = "0001_add_user_role"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "whatsapp_auth_state",
        sa.Column("id", sa.Integer, primary_key=True, server_default=sa.text("1")),
        sa.Column("state", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column(
            "last_updated",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Seed the single row
    op.execute(
        "INSERT INTO whatsapp_auth_state (id) VALUES (1) "
        "ON CONFLICT (id) DO NOTHING"
    )


def downgrade():
    op.drop_table("whatsapp_auth_state")
