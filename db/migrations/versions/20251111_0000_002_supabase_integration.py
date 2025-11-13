"""Add Supabase integration to users table

Revision ID: 20251111_0000_002
Revises: 20251110_2100_001
Create Date: 2025-11-11 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20251111_0000_002'
down_revision: Union[str, None] = '20251110_2100_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if column already exists (may have been added in initial migration)
    # This makes the migration idempotent
    from sqlalchemy import inspect
    from alembic import context

    conn = context.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('users')]

    if 'supabase_user_id' not in columns:
        # Add supabase_user_id column to users table
        op.add_column(
            'users',
            sa.Column('supabase_user_id', postgresql.UUID(as_uuid=True), nullable=True, unique=True)
        )

        # Create index on supabase_user_id for faster lookups
        op.create_index('idx_users_supabase_user_id', 'users', ['supabase_user_id'], unique=True)

    # Add comment to document the change (safe to run even if column exists)
    op.execute("""
        COMMENT ON COLUMN users.supabase_user_id IS
        'Supabase Auth user ID for linking with Supabase authentication.
        This allows us to maintain our own user data while delegating auth to Supabase.'
    """)


def downgrade() -> None:
    # Remove index
    op.drop_index('idx_users_supabase_user_id', 'users')

    # Remove column
    op.drop_column('users', 'supabase_user_id')
