"""Remove users table and use Supabase as single source of truth

Revision ID: 2511140852_009
Revises: 20251114_0000_008
Create Date: 2025-11-14 08:52:00.000000

This migration removes the local users table and migrates to using Supabase
as the single source of truth for all user data. All user_id foreign keys
are converted to plain UUIDs representing supabase_user_id.

Changes:
- Drop FK constraints from videos, face_profiles, audit_events
- Drop refresh_tokens table (Supabase handles refresh tokens)
- Drop email_verification_tokens table (Supabase handles email verification)
- Drop users table completely
- All user profile data will be stored in Supabase user_metadata

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2511140852_009'
down_revision: Union[str, None] = '20251114_0000_008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Migrate from local users table to Supabase-only user management."""

    # Step 1: Drop foreign key constraints
    print("Dropping foreign key constraints...")

    # Videos table
    op.drop_constraint('videos_user_id_fkey', 'videos', type_='foreignkey')

    # Face profiles table
    op.drop_constraint('face_profiles_user_id_fkey', 'face_profiles', type_='foreignkey')

    # Audit events table (has SET NULL, so it's safe to drop)
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT IF EXISTS audit_events_user_id_fkey")

    # Rate limits table (may not have FK)
    op.execute("ALTER TABLE rate_limits DROP CONSTRAINT IF EXISTS rate_limits_user_id_fkey")

    # Step 2: Drop auth-related tables (Supabase handles these)
    print("Dropping auth tables (Supabase handles these)...")

    op.drop_table('refresh_tokens')
    op.drop_table('email_verification_tokens')

    # Step 3: Drop indexes on users table
    print("Dropping users table indexes...")

    op.drop_index('idx_users_email', 'users')
    op.drop_index('idx_users_supabase_user_id', 'users')

    # Step 4: Drop user_tier enum type (will be managed in Supabase)
    print("Dropping user_tier enum...")

    op.execute("DROP TYPE IF EXISTS user_tier CASCADE")

    # Step 5: Drop the users table
    print("Dropping users table...")

    op.drop_table('users')

    print("Migration complete: Users table removed, Supabase is now single source of truth")


def downgrade() -> None:
    """Recreate users table and restore foreign keys.

    WARNING: This downgrade will NOT restore user data. You would need to
    resync from Supabase or restore from backup.
    """

    # Recreate user_tier enum
    op.execute("CREATE TYPE user_tier AS ENUM ('free', 'pro', 'enterprise')")

    # Recreate users table
    op.create_table(
        'users',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('supabase_user_id', postgresql.UUID(as_uuid=True), nullable=True, unique=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('avatar_url', sa.String(512), nullable=True),
        sa.Column('tier', sa.Enum('free', 'pro', 'enterprise', name='user_tier'), nullable=False, server_default='free'),
        sa.Column('industry', sa.String(100), nullable=True),
        sa.Column('job_title', sa.String(100), nullable=True),
        sa.Column('email_consent', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('onboarding_completed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('last_login_at', sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_supabase_user_id', 'users', ['supabase_user_id'])

    # Recreate refresh_tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('token_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('token_hash', sa.String(255), nullable=False, unique=True),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('revoked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    )
    op.create_index('idx_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])
    op.create_index('idx_refresh_tokens_token_hash', 'refresh_tokens', ['token_hash'])
    op.create_index('idx_refresh_tokens_expires_at', 'refresh_tokens', ['expires_at'])

    # Recreate email_verification_tokens table
    op.create_table(
        'email_verification_tokens',
        sa.Column('token_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('token_hash', sa.String(255), nullable=False, unique=True),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    )
    op.create_index('idx_email_verification_tokens_token_hash', 'email_verification_tokens', ['token_hash'])

    # Restore foreign keys (NOTE: Will fail if user_id values don't match users table)
    op.create_foreign_key('videos_user_id_fkey', 'videos', 'users', ['user_id'], ['user_id'], ondelete='CASCADE')
    op.create_foreign_key('face_profiles_user_id_fkey', 'face_profiles', 'users', ['user_id'], ['user_id'], ondelete='CASCADE')

    print("WARNING: Downgrade completed but user data was NOT restored. You must resync from Supabase or restore from backup.")
