"""Add user onboarding fields

Revision ID: 20251114_0000_008
Revises: 20251112_0257_007
Create Date: 2025-11-14 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20251114_0000_008'
down_revision: Union[str, None] = '20251112_0257_007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add onboarding fields to users table."""
    # Add industry field
    op.add_column('users', sa.Column('industry', sa.String(100), nullable=True))

    # Add job_title field
    op.add_column('users', sa.Column('job_title', sa.String(100), nullable=True))

    # Add email_consent field (default false)
    op.add_column('users', sa.Column('email_consent', sa.Boolean(), nullable=False, server_default='false'))

    # Add onboarding_completed field (default false)
    op.add_column('users', sa.Column('onboarding_completed', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    """Remove onboarding fields from users table."""
    op.drop_column('users', 'onboarding_completed')
    op.drop_column('users', 'email_consent')
    op.drop_column('users', 'job_title')
    op.drop_column('users', 'industry')
