-- ==========================================
-- INSIGHT - Semantic Talent Finder
-- Migration 004: Performance Indexes
-- ==========================================
-- Build indexes AFTER data load for better performance
-- Use CONCURRENTLY for online index creation if needed

-- ==================== VECTOR INDEXES ====================

-- HNSW index for approximate nearest neighbor search
-- m=16: number of connections per layer (higher = better recall, more memory)
-- ef_construction=64: quality vs speed tradeoff during index build
CREATE INDEX IF NOT EXISTS idx_profiles_embedding_hnsw
ON profiles USING hnsw (embedding vector_cosine_ops)
WITH (m=16, ef_construction=64);

COMMENT ON INDEX idx_profiles_embedding_hnsw IS
'HNSW ANN index for vector similarity search.
Set hnsw.ef_search=64 at query time for quality/speed balance.';

-- ==================== GIN INDEXES (Arrays & FTS) ====================

-- Skills array index for @> (contains) queries
CREATE INDEX IF NOT EXISTS idx_profiles_skills
ON profiles USING GIN (skills);

COMMENT ON INDEX idx_profiles_skills IS
'GIN index for skills array containment queries.
Enables: WHERE skills @> ARRAY[''python'', ''nlp'']';

-- Normalized skills for fuzzy matching
CREATE INDEX IF NOT EXISTS idx_profiles_skills_normalized
ON profiles USING GIN (skills_normalized);

-- Full-text search index on searchable text fields
CREATE INDEX IF NOT EXISTS idx_profiles_fts
ON profiles USING GIN (
    to_tsvector('english',
        coalesce(full_name, '') || ' ' ||
        coalesce(headline, '') || ' ' ||
        coalesce(summary, '') || ' ' ||
        coalesce(job_title, '') || ' ' ||
        coalesce(company_name, '')
    )
);

COMMENT ON INDEX idx_profiles_fts IS
'Full-text search index for lexical matching (ts_rank).
Combines: name, headline, summary, title, company.';

-- ==================== B-TREE INDEXES (Filters) ====================

-- Geographic filters (composite for multi-level search)
CREATE INDEX IF NOT EXISTS idx_profiles_location
ON profiles (location_country, region, locality)
WHERE location_country IS NOT NULL;

COMMENT ON INDEX idx_profiles_location IS
'Composite geographic index for hierarchical location filtering.
Enables country → region → locality drill-down.';

-- Job title for exact/prefix matching
CREATE INDEX IF NOT EXISTS idx_profiles_title
ON profiles (job_title)
WHERE job_title IS NOT NULL;

-- Company name for filtering
CREATE INDEX IF NOT EXISTS idx_profiles_company
ON profiles (company_name)
WHERE company_name IS NOT NULL;

-- Industry for filtering
CREATE INDEX IF NOT EXISTS idx_profiles_industry
ON profiles (industry)
WHERE industry IS NOT NULL;

-- Years of experience for range queries
CREATE INDEX IF NOT EXISTS idx_profiles_experience
ON profiles (years_experience)
WHERE years_experience IS NOT NULL;

-- Quality score for filtering low-quality profiles
CREATE INDEX IF NOT EXISTS idx_profiles_quality
ON profiles (content_quality_score)
WHERE content_quality_score IS NOT NULL;

-- Soft delete filter (most queries exclude deleted)
CREATE INDEX IF NOT EXISTS idx_profiles_not_deleted
ON profiles (is_deleted)
WHERE is_deleted = FALSE;

-- LinkedIn username (natural key, for lookups)
CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_linkedin_username
ON profiles (linkedin_username);

-- ==================== FOREIGN KEY INDEXES ====================

-- Profile experiences - profile lookup
CREATE INDEX IF NOT EXISTS idx_experiences_profile
ON profile_experiences (profile_id);

-- Profile experiences - company lookup
CREATE INDEX IF NOT EXISTS idx_experiences_company
ON profile_experiences (company_id)
WHERE company_id IS NOT NULL;

-- Profile education - profile lookup
CREATE INDEX IF NOT EXISTS idx_education_profile
ON profile_education (profile_id);

-- Profile certifications - profile lookup
CREATE INDEX IF NOT EXISTS idx_certifications_profile
ON profile_certifications (profile_id);

-- ==================== TIMESTAMP INDEXES ====================

-- Created timestamp for time-series queries
CREATE INDEX IF NOT EXISTS idx_profiles_created
ON profiles (created_at DESC);

-- Updated timestamp for incremental updates
CREATE INDEX IF NOT EXISTS idx_profiles_updated
ON profiles (updated_at DESC);

-- ==================== COMPANIES TABLE INDEXES ====================

-- Company name (unique already has index, but explicit)
CREATE INDEX IF NOT EXISTS idx_companies_industry
ON companies (industry)
WHERE industry IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_companies_country
ON companies (headquarters_country)
WHERE headquarters_country IS NOT NULL;

-- ==================== INDEX STATISTICS ====================

-- Update statistics for query planner
ANALYZE profiles;
ANALYZE companies;
ANALYZE profile_experiences;
ANALYZE profile_education;
ANALYZE profile_certifications;

-- Display index sizes for monitoring
SELECT
    schemaname,
    relname as tablename,
    indexrelname as indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY pg_relation_size(indexrelid) DESC;
