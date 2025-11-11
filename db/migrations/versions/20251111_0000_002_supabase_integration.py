"""Add Supabase integration to users table

Revision ID: 002
Revises: 001
Create Date: 2025-11-11 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add supabase_user_id column to users table
    op.add_column(
        'users',
        sa.Column('supabase_user_id', postgresql.UUID(as_uuid=True), nullable=True, unique=True)
    )

    # Create index on supabase_user_id for faster lookups
    op.create_index('idx_users_supabase_user_id', 'users', ['supabase_user_id'], unique=True)

    # Make password_hash nullable since Supabase handles authentication
    # (it's already nullable in the initial migration, so this is a no-op but documented for clarity)

    # Add comment to document the change
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
