"""fix image_vec dimensions for SigLIP

Revision ID: 20251111_0000_004
Revises: 20251111_0100_003
Create Date: 2025-11-11 00:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251111_0000_004'
down_revision = '20251111_0100_003'
branch_labels = None
depends_on = None


def upgrade():
    """Change image_vec from vector(512) to vector(1152) for SigLIP so400m."""
    # SigLIP so400m-patch14-384 produces 1152-dimensional embeddings
    # Check current dimension of image_vec column
    from alembic import context
    conn = context.get_bind()

    result = conn.execute(sa.text("""
        SELECT atttypmod
        FROM pg_attribute
        WHERE attrelid = 'scenes'::regclass
        AND attname = 'image_vec'
    """))
    row = result.fetchone()

    # atttypmod for vector(n) is n + 4, so vector(512) has atttypmod 516
    # Only update if current dimension is not 1152
    if row and row[0] != 1156:  # 1152 + 4 = 1156
        op.execute('ALTER TABLE scenes ALTER COLUMN image_vec TYPE vector(1152) USING image_vec::vector(1152)')


def downgrade():
    """Revert image_vec back to vector(512)."""
    op.execute('ALTER TABLE scenes ALTER COLUMN image_vec TYPE vector(512) USING image_vec::vector(512)')
