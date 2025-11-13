"""Create video_metadata table for video titles, descriptions, and tags

Revision ID: 20251111_0100_003
Revises: 20251111_0000_002
Create Date: 2025-11-11 01:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20251111_0100_003'
down_revision: Union[str, None] = '20251111_0000_002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create video_metadata table for storing video titles, descriptions, and tags."""
    # Check if table already exists
    from sqlalchemy import inspect
    from alembic import context

    conn = context.get_bind()
    inspector = inspect(conn)

    if 'video_metadata' not in inspector.get_table_names():
        op.create_table(
            'video_metadata',
            sa.Column('video_id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('title', sa.String(255), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('tags', postgresql.JSONB(), nullable=True),
            sa.Column('thumbnail_url', sa.String(512), nullable=True),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.ForeignKeyConstraint(['video_id'], ['videos.video_id'], ondelete='CASCADE'),
        )


def downgrade() -> None:
    """Remove video_metadata table."""
    op.drop_table('video_metadata')
