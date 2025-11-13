-- Create schema for Heimdex B2C
-- Based on migration 20251110_2100_001_initial_schema

-- Create enum types (lowercase values to match SQLAlchemy enum values, not names)
CREATE TYPE user_tier AS ENUM ('free', 'pro', 'enterprise');
CREATE TYPE video_state AS ENUM ('uploading', 'validating', 'processing', 'indexed', 'failed', 'deleted');
CREATE TYPE job_stage AS ENUM ('upload_validate', 'audio_extract', 'asr_fast', 'scene_detect', 'align_merge', 'embed_text', 'vision_sample_frames', 'vision_embed_frames', 'vision_affect_tags', 'faces_enroll_match', 'sidecar_build', 'commit');
CREATE TYPE job_state AS ENUM ('pending', 'running', 'completed', 'failed', 'cancelled');

-- Users table
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    supabase_user_id UUID UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    email_verified BOOLEAN NOT NULL DEFAULT false,
    password_hash VARCHAR(255),
    display_name VARCHAR(255),
    avatar_url VARCHAR(512),
    tier user_tier NOT NULL DEFAULT 'free',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_supabase_user_id ON users(supabase_user_id);

-- Videos table
CREATE TABLE videos (
    video_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    storage_key VARCHAR(512) NOT NULL,
    mime_type VARCHAR(127) NOT NULL,
    size_bytes BIGINT NOT NULL,
    duration_s NUMERIC(10, 3),
    state video_state NOT NULL DEFAULT 'uploading',
    error_text TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    indexed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_videos_user_id ON videos(user_id);
CREATE INDEX idx_videos_state ON videos(state);
CREATE INDEX idx_videos_created_at ON videos(created_at);

-- Scenes table
CREATE TABLE scenes (
    scene_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id UUID NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    start_s NUMERIC(10, 3) NOT NULL,
    end_s NUMERIC(10, 3) NOT NULL,
    transcript TEXT,
    tsv TSVECTOR,
    text_vec VECTOR(1024),
    image_vec VECTOR(1152),
    vision_tags JSONB,
    sidecar_key VARCHAR(512),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_scenes_video_id ON scenes(video_id);
CREATE INDEX idx_scenes_video_start ON scenes(video_id, start_s);
CREATE INDEX idx_scenes_vision_tags ON scenes USING GIN (vision_tags jsonb_path_ops);
CREATE INDEX idx_scenes_tsv ON scenes USING GIN (tsv);

-- Jobs table
CREATE TABLE jobs (
    job_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id UUID NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    stage job_stage NOT NULL,
    state job_state NOT NULL DEFAULT 'pending',
    progress INTEGER NOT NULL DEFAULT 0,
    error_text TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    finished_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_jobs_video_id ON jobs(video_id);
CREATE INDEX idx_jobs_state ON jobs(state);

-- Face profiles table
CREATE TABLE face_profiles (
    face_profile_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    photo_url VARCHAR(512),
    face_vec VECTOR(512),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_face_profiles_user_id ON face_profiles(user_id);

-- Face detections table
CREATE TABLE face_detections (
    face_detection_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scene_id UUID NOT NULL REFERENCES scenes(scene_id) ON DELETE CASCADE,
    face_profile_id UUID REFERENCES face_profiles(face_profile_id) ON DELETE SET NULL,
    bbox JSONB NOT NULL,
    face_vec VECTOR(512),
    confidence REAL NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_face_detections_scene_id ON face_detections(scene_id);
CREATE INDEX idx_face_detections_profile_id ON face_detections(face_profile_id);

-- Audit events table
CREATE TABLE audit_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    event_type VARCHAR(63) NOT NULL,
    resource_type VARCHAR(63),
    resource_id UUID,
    metadata JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_events_user_id ON audit_events(user_id);
CREATE INDEX idx_audit_events_type ON audit_events(event_type);
CREATE INDEX idx_audit_events_created_at ON audit_events(created_at);

-- Refresh tokens table
CREATE TABLE refresh_tokens (
    token_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_hash ON refresh_tokens(token_hash);

-- Email verification tokens table
CREATE TABLE email_verification_tokens (
    token_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_email_verification_tokens_user_id ON email_verification_tokens(user_id);
CREATE INDEX idx_email_verification_tokens_hash ON email_verification_tokens(token_hash);

-- Video metadata table (title, description, tags)
CREATE TABLE video_metadata (
    video_id UUID PRIMARY KEY REFERENCES videos(video_id) ON DELETE CASCADE,
    title VARCHAR(255),
    description TEXT,
    tags JSONB,
    thumbnail_url VARCHAR(512),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
