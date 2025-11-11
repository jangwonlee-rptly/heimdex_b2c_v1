"""Initial schema with users, videos, scenes, jobs, face_profiles, and audit tables

Revision ID: 001
Revises:
Create Date: 2025-11-10 21:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('password_hash', sa.String(255), nullable=True),  # Nullable for magic link only users
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('avatar_url', sa.String(512), nullable=True),
        sa.Column('tier', sa.Enum('free', 'pro', 'enterprise', name='user_tier'), nullable=False, server_default='free'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('last_login_at', sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index('idx_users_email', 'users', ['email'])

    # Videos table
    op.create_table(
        'videos',
        sa.Column('video_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('storage_key', sa.String(512), nullable=False),
        sa.Column('mime_type', sa.String(127), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('duration_s', sa.Numeric(10, 3), nullable=True),  # Set after validation
        sa.Column('state', sa.Enum('uploading', 'validating', 'processing', 'indexed', 'failed', 'deleted', name='video_state'), nullable=False, server_default='uploading'),
        sa.Column('error_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('indexed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    )
    op.create_index('idx_videos_user_id', 'videos', ['user_id'])
    op.create_index('idx_videos_state', 'videos', ['state'])
    op.create_index('idx_videos_created_at', 'videos', ['created_at'])

    # Scenes table
    op.create_table(
        'scenes',
        sa.Column('scene_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('video_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('start_s', sa.Numeric(10, 3), nullable=False),
        sa.Column('end_s', sa.Numeric(10, 3), nullable=False),
        sa.Column('transcript', sa.Text(), nullable=True),
        sa.Column('tsv', postgresql.TSVECTOR(), nullable=True),  # For PGroonga or tsvector
        sa.Column('text_vec', postgresql.ARRAY(sa.Float()), nullable=True),  # Will be converted to vector type
        sa.Column('image_vec', postgresql.ARRAY(sa.Float()), nullable=True),  # Will be converted to vector type
        sa.Column('vision_tags', postgresql.JSONB(), nullable=True),
        sa.Column('sidecar_key', sa.String(512), nullable=True),  # Storage key for immutable sidecar JSON
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['video_id'], ['videos.video_id'], ondelete='CASCADE'),
    )
    op.create_index('idx_scenes_video_id', 'scenes', ['video_id'])
    op.create_index('idx_scenes_video_start', 'scenes', ['video_id', 'start_s'])
    op.create_index('idx_scenes_vision_tags', 'scenes', ['vision_tags'], postgresql_using='gin', postgresql_ops={'vision_tags': 'jsonb_path_ops'})

    # Convert array columns to vector type (requires pgvector extension)
    op.execute('ALTER TABLE scenes ALTER COLUMN text_vec TYPE vector(1024) USING text_vec::vector(1024)')
    op.execute('ALTER TABLE scenes ALTER COLUMN image_vec TYPE vector(512) USING image_vec::vector(512)')

    # Try to create PGroonga index, fallback to tsvector if PGroonga not available
    op.execute("""
        DO $$
        BEGIN
            -- Try PGroonga index
            CREATE INDEX idx_scenes_transcript_pgroonga ON scenes USING pgroonga (transcript);
            RAISE NOTICE 'Created PGroonga index on transcript';
        EXCEPTION WHEN OTHERS THEN
            -- Fallback to PostgreSQL tsvector
            CREATE INDEX idx_scenes_tsv ON scenes USING gin (tsv);
            RAISE WARNING 'PGroonga not available, using tsvector index';
        END;
        $$;
    """)

    # Jobs table (for tracking indexing progress)
    op.create_table(
        'jobs',
        sa.Column('job_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('video_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('stage', sa.Enum('upload_validate', 'audio_extract', 'asr_fast', 'scene_detect', 'align_merge', 'embed_text', 'vision_sample_frames', 'vision_embed_frames', 'vision_affect_tags', 'faces_enroll_match', 'sidecar_build', 'commit', name='job_stage'), nullable=False),
        sa.Column('state', sa.Enum('pending', 'running', 'completed', 'failed', 'cancelled', name='job_state'), nullable=False, server_default='pending'),
        sa.Column('progress', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('error_text', sa.Text(), nullable=True),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('finished_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),  # For stage-specific metadata
        sa.ForeignKeyConstraint(['video_id'], ['videos.video_id'], ondelete='CASCADE'),
    )
    op.create_index('idx_jobs_video_id', 'jobs', ['video_id'])
    op.create_index('idx_jobs_state', 'jobs', ['state'])

    # Face profiles table
    op.create_table(
        'face_profiles',
        sa.Column('person_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('adaface_vec', postgresql.ARRAY(sa.Float()), nullable=True),  # Will be converted to vector type
        sa.Column('photo_keys', postgresql.ARRAY(sa.String()), nullable=True),  # Storage keys for enrollment photos
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    )
    op.create_index('idx_face_profiles_user_id', 'face_profiles', ['user_id'])

    # Convert adaface_vec to vector type
    op.execute('ALTER TABLE face_profiles ALTER COLUMN adaface_vec TYPE vector(512) USING adaface_vec::vector(512)')

    # Scene-people association table (many-to-many)
    op.create_table(
        'scene_people',
        sa.Column('scene_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('person_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),  # Face match confidence
        sa.Column('frame_count', sa.Integer(), nullable=False),  # Number of frames where person detected
        sa.PrimaryKeyConstraint('scene_id', 'person_id'),
        sa.ForeignKeyConstraint(['scene_id'], ['scenes.scene_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['person_id'], ['face_profiles.person_id'], ondelete='CASCADE'),
    )
    op.create_index('idx_scene_people_person_id', 'scene_people', ['person_id'])

    # Refresh tokens table (for JWT refresh token rotation)
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

    # Email verification tokens
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

    # Audit events table (for security and compliance)
    op.create_table(
        'audit_events',
        sa.Column('event_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),  # Nullable for anonymous events
        sa.Column('event_type', sa.String(127), nullable=False),  # e.g., 'user.login', 'video.upload', 'search.query'
        sa.Column('ip_address', sa.String(45), nullable=True),  # IPv4 or IPv6
        sa.Column('user_agent', sa.String(512), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('idx_audit_events_user_id', 'audit_events', ['user_id'])
    op.create_index('idx_audit_events_event_type', 'audit_events', ['event_type'])
    op.create_index('idx_audit_events_created_at', 'audit_events', ['created_at'])

    # Rate limiting table (for per-user quotas)
    op.create_table(
        'rate_limits',
        sa.Column('limit_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),  # Nullable for IP-based limits
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('resource', sa.String(127), nullable=False),  # e.g., 'upload', 'search'
        sa.Column('count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('window_start', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_index('idx_rate_limits_user_resource', 'rate_limits', ['user_id', 'resource', 'window_start'])
    op.create_index('idx_rate_limits_ip_resource', 'rate_limits', ['ip_address', 'resource', 'window_start'])
    op.create_index('idx_rate_limits_expires_at', 'rate_limits', ['expires_at'])


def downgrade() -> None:
    op.drop_table('rate_limits')
    op.drop_table('audit_events')
    op.drop_table('email_verification_tokens')
    op.drop_table('refresh_tokens')
    op.drop_table('scene_people')
    op.drop_table('face_profiles')
    op.drop_table('jobs')
    op.drop_table('scenes')
    op.drop_table('videos')
    op.drop_table('users')

    op.execute('DROP TYPE IF EXISTS job_state')
    op.execute('DROP TYPE IF EXISTS job_stage')
    op.execute('DROP TYPE IF EXISTS video_state')
    op.execute('DROP TYPE IF EXISTS user_tier')
