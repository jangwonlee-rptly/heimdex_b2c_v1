"""add HNSW vector indexes for ANN search

Revision ID: 20251112_0257_007
Revises: 20251112_0200_006
Create Date: 2025-11-12 02:57

FEATURE FLAG: search_sys_ann_tuning

This migration adds HNSW (Hierarchical Navigable Small World) indexes
to vector columns for efficient approximate nearest neighbor search.

Performance Impact:
- Sequential scan: O(N) with N scenes
- HNSW: O(log N) query time with configurable accuracy/speed tradeoff

Index Parameters:
- m=16: Max connections per layer (default, balanced)
- ef_construction=64: Build-time accuracy (higher = better index, slower build)

Query Parameters (set at query time, not in index):
- ef_search: Runtime search breadth (config: search_ann_ef_search, default 100)

Rollback Plan:
1. Set FEATURE_SEARCH_SYS_ANN_TUNING=false
2. Run: psql -d heimdex -c "DROP INDEX CONCURRENTLY IF EXISTS idx_scenes_image_vec_hnsw;"
3. Run: psql -d heimdex -c "DROP INDEX CONCURRENTLY IF EXISTS idx_scenes_text_vec_hnsw;"
4. Run downgrade migration

Reference: https://github.com/pgvector/pgvector#hnsw
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '20251112_0257_007'
down_revision = '20251112_0200_006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create HNSW indexes on vector columns for fast ANN search.

    Uses CONCURRENTLY to avoid blocking writes during index creation.
    Safe for production deployment.
    """
    # Create HNSW index on image_vec (vision embeddings) - 1152 dimensions
    # m=16: Each vector connected to ~16 neighbors (balanced speed/accuracy)
    # ef_construction=64: Build quality (higher = better index, slower build)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_scenes_image_vec_hnsw
        ON scenes USING hnsw (image_vec vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # Create HNSW index on text_vec (text embeddings) - 1152 dimensions
    # Same parameters as image_vec for consistency
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_scenes_text_vec_hnsw
        ON scenes USING hnsw (text_vec vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # Note: ef_search (query-time parameter) is set in app config, not in index
    # See api/app/config.py: search_ann_ef_search


def downgrade() -> None:
    """
    Drop HNSW indexes (fall back to sequential scan).

    Uses CONCURRENTLY to avoid blocking operations.
    """
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_scenes_image_vec_hnsw")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_scenes_text_vec_hnsw")
