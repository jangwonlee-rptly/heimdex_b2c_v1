-- Initialize PostgreSQL extensions for Heimdex B2C
-- Run on database initialization

-- Enable pgvector for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable citext for case-insensitive email comparisons
CREATE EXTENSION IF NOT EXISTS citext;

-- Enable uuid-ossp for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Note: PGroonga requires manual installation on the PostgreSQL image
-- For dev: Use a custom Dockerfile based on pgvector/pgvector:pg16
-- Instructions at: https://pgroonga.github.io/install/

-- Attempt to enable PGroonga (will fail if not installed)
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS pgroonga;
    RAISE NOTICE 'PGroonga extension enabled successfully';
EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'PGroonga extension not available. Install it for full-text search support.';
    RAISE WARNING 'Falling back to PostgreSQL built-in tsvector for text search.';
END;
$$;

-- Create schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- Insert initial version
INSERT INTO schema_version (version, description)
VALUES (1, 'Initial schema with pgvector and PGroonga support')
ON CONFLICT (version) DO NOTHING;
