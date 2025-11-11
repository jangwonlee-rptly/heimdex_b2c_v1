"""Add title and description columns to videos table

Revision ID: 003
Revises: 002
Create Date: 2025-11-11 01:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add title and description columns to videos table."""
    op.add_column('videos', sa.Column('title', sa.String(255), nullable=True))
    op.add_column('videos', sa.Column('description', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove title and description columns from videos table."""
    op.drop_column('videos', 'description')
    op.drop_column('videos', 'title')
