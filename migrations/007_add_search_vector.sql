-- Migration: Add pre-computed full-text search vector for 100x faster text queries
-- This eliminates the need to compute to_tsvector() on every search

-- Add tsvector column for pre-computed search
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS search_vector tsvector;

-- Create index on the tsvector column (GIN index for fast full-text search)
CREATE INDEX IF NOT EXISTS idx_profiles_search_vector
    ON profiles USING GIN (search_vector);

-- Populate the search_vector column for existing rows
UPDATE profiles
SET search_vector = to_tsvector('english',
    coalesce(full_name, '') || ' ' ||
    coalesce(headline, '') || ' ' ||
    coalesce(summary, '') || ' ' ||
    coalesce(job_title, '') || ' ' ||
    coalesce(company_name, '')
)
WHERE search_vector IS NULL;

-- Create trigger function to auto-update search_vector on INSERT/UPDATE
CREATE OR REPLACE FUNCTION profiles_search_vector_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector := to_tsvector('english',
        coalesce(NEW.full_name, '') || ' ' ||
        coalesce(NEW.headline, '') || ' ' ||
        coalesce(NEW.summary, '') || ' ' ||
        coalesce(NEW.job_title, '') || ' ' ||
        coalesce(NEW.company_name, '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to auto-update search_vector
DROP TRIGGER IF EXISTS profiles_search_vector_trigger ON profiles;
CREATE TRIGGER profiles_search_vector_trigger
    BEFORE INSERT OR UPDATE OF full_name, headline, summary, job_title, company_name
    ON profiles
    FOR EACH ROW
    EXECUTE FUNCTION profiles_search_vector_update();

-- Add composite index for common filter combinations
CREATE INDEX IF NOT EXISTS idx_profiles_multi_filter
    ON profiles(is_deleted, location_country, region, industry)
    WHERE is_deleted = FALSE;

-- Analyze table to update statistics
ANALYZE profiles;
