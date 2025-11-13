"""Add thumbnail_key to scenes table

Revision ID: 20251112_0200_006
Revises: 20251111_1530_005
Create Date: 2025-11-12 02:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251112_0200_006'
down_revision = '20251111_1530_005'
branch_labels = None
depends_on = None


def upgrade():
    """Add thumbnail_key column to scenes table."""
    # Check if column already exists (may have been added manually)
    from sqlalchemy import inspect
    from alembic import context

    conn = context.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('scenes')]

    if 'thumbnail_key' not in columns:
        op.add_column('scenes', sa.Column('thumbnail_key', sa.String(length=512), nullable=True,
                                          comment='Storage key for scene thumbnail image (WebP format)'))


def downgrade():
    """Remove thumbnail_key column from scenes table."""
    op.drop_column('scenes', 'thumbnail_key')
