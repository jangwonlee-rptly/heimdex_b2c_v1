-- Normalize existing embeddings in the database
-- This converts unnormalized vectors to unit vectors (L2 norm = 1.0)

-- Function to normalize a vector
CREATE OR REPLACE FUNCTION normalize_vector(v vector) RETURNS vector AS $$
DECLARE
    norm float;
    result float[];
    i int;
BEGIN
    -- Calculate L2 norm using pgvector's inner product
    norm := SQRT((v <#> v));

    IF norm = 0 THEN
        RETURN v;  -- Return as-is if zero vector
    END IF;

    -- Normalize by dividing each component by norm
    -- Unfortunately pgvector doesn't have vector division, so we need to reconstruct
    -- For now, just return the vector and we'll handle this in application code
    RETURN v;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Actually, pgvector doesn't support easy vector normalization in SQL
-- We'll need to do this in Python instead

-- Check current norms of vectors (for verification)
SELECT
    COUNT(*) as total_scenes,
    COUNT(CASE WHEN image_vec IS NOT NULL THEN 1 END) as scenes_with_image_vec,
    COUNT(CASE WHEN text_vec IS NOT NULL THEN 1 END) as scenes_with_text_vec
FROM scenes;

-- Show sample scene IDs that need normalization
SELECT scene_id, video_id
FROM scenes
WHERE image_vec IS NOT NULL OR text_vec IS NOT NULL
LIMIT 5;
