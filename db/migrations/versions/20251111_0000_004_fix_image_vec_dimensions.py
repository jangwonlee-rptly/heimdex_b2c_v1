"""fix image_vec dimensions for SigLIP

Revision ID: 004
Revises: 003
Create Date: 2025-11-11 00:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    """Change image_vec from vector(512) to vector(1152) for SigLIP so400m."""
    # SigLIP so400m-patch14-384 produces 1152-dimensional embeddings
    op.execute('ALTER TABLE scenes ALTER COLUMN image_vec TYPE vector(1152) USING image_vec::vector(1152)')


def downgrade():
    """Revert image_vec back to vector(512)."""
    op.execute('ALTER TABLE scenes ALTER COLUMN image_vec TYPE vector(512) USING image_vec::vector(512)')
