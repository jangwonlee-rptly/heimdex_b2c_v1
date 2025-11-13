"""update text_vec dimensions to 1152 for SigLIP

Revision ID: 20251111_1530_005
Revises: 20251111_0000_004
Create Date: 2025-11-11 15:30:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251111_1530_005'
down_revision = '20251111_0000_004'
branch_labels = None
depends_on = None


def upgrade():
    """Change text_vec from vector(1024) to vector(1152) for SigLIP.

    We're now using SigLIP (so400m-patch14-384) for both text and vision embeddings,
    which produces 1152-dimensional embeddings instead of BGE-M3's 1024 dimensions.
    """
    # Check current dimension of text_vec column
    from alembic import context
    conn = context.get_bind()

    result = conn.execute(sa.text("""
        SELECT atttypmod
        FROM pg_attribute
        WHERE attrelid = 'scenes'::regclass
        AND attname = 'text_vec'
    """))
    row = result.fetchone()

    # atttypmod for vector(n) is n + 4, so vector(1024) has atttypmod 1028
    # Only update if current dimension is not 1152
    if row and row[0] != 1156:  # 1152 + 4 = 1156
        # Drop existing vectors as they are incompatible with new dimensions
        op.execute('UPDATE scenes SET text_vec = NULL WHERE text_vec IS NOT NULL')

        # Change column type
        op.execute('ALTER TABLE scenes ALTER COLUMN text_vec TYPE vector(1152)')


def downgrade():
    """Revert text_vec back to vector(1024)."""
    # Drop existing vectors as they are incompatible with old dimensions
    op.execute('UPDATE scenes SET text_vec = NULL WHERE text_vec IS NOT NULL')

    # Revert column type
    op.execute('ALTER TABLE scenes ALTER COLUMN text_vec TYPE vector(1024)')
