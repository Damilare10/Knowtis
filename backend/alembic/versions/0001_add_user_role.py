"""Add user role enum and column

Revision ID: 0001_add_user_role
Revises: None
Create Date: 2026-07-07 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001_add_user_role"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create enum type safely (no-op if exists)
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN
            CREATE TYPE userrole AS ENUM ('student', 'admin');
        END IF;
    END$$;
    """)

    # Add role column with server default so existing rows get 'student'
    op.add_column(
        'users',
        sa.Column('role', sa.Enum('student', 'admin', name='userrole'), nullable=False, server_default='student'),
    )

    # Ensure the server default remains explicitly set to 'student'
    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'student';")


def downgrade():
    # Drop the column then drop the type if present
    op.drop_column('users', 'role')
    op.execute("DROP TYPE IF EXISTS userrole;")
