"""Add thumbnail_key to scenes table

Revision ID: 006
Revises: 005
Create Date: 2025-11-12 02:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    """Add thumbnail_key column to scenes table."""
    op.add_column('scenes', sa.Column('thumbnail_key', sa.String(length=512), nullable=True,
                                      comment='Storage key for scene thumbnail image (WebP format)'))


def downgrade():
    """Remove thumbnail_key column from scenes table."""
    op.drop_column('scenes', 'thumbnail_key')
