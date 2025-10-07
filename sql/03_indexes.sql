-- INSIGHT - Index Strategy (Build AFTER Bulk Load)
-- M2-optimized HNSW parameters: m=16, ef_construction=200

-- IMPORTANT: Build indexes in this order for optimal performance
-- 1. Primary filters (most selective first)
-- 2. Composite indexes (common filter combinations)
-- 3. GIN indexes (arrays, full-text)
-- 4. Trigram indexes (fuzzy matching)
-- 5. HNSW index (LAST - most expensive)

-- Before building indexes, increase maintenance memory:
-- SET maintenance_work_mem = '4GB';

-- =============================================================================
-- PRIMARY FILTERS
-- =============================================================================

-- Quality score (used in almost all queries)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hot_quality_score
    ON profiles_hot(quality_score DESC)
    WHERE is_deleted = FALSE AND quality_score >= 0.7;

-- Country (high selectivity)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hot_country
    ON profiles_hot(location_country)
    WHERE is_deleted = FALSE;

-- Industry (high selectivity)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hot_industry
    ON profiles_hot(industry)
    WHERE is_deleted = FALSE;

-- Seniority level
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hot_seniority
    ON profiles_hot(seniority_level)
    WHERE is_deleted = FALSE;

-- Years experience (range queries)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hot_experience
    ON profiles_hot(years_experience)
    WHERE is_deleted = FALSE;

-- =============================================================================
-- COMPOSITE INDEXES (Common Filter Combinations)
-- =============================================================================

-- Country + Industry (very common combination)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hot_country_industry
    ON profiles_hot(location_country, industry)
    WHERE is_deleted = FALSE;

-- Country + Seniority
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hot_country_seniority
    ON profiles_hot(location_country, seniority_level)
    WHERE is_deleted = FALSE;

-- Industry + Seniority
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hot_industry_seniority
    ON profiles_hot(industry, seniority_level)
    WHERE is_deleted = FALSE;

-- Hotness score (for promotion/demotion)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hot_hotness_score
    ON profiles_hot(hotness_score DESC)
    WHERE is_deleted = FALSE;

-- =============================================================================
-- GIN INDEXES (Arrays and Full-Text)
-- =============================================================================

-- Skills array (containment queries: top_skills && ARRAY['Python'])
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hot_skills_gin
    ON profiles_hot USING GIN(top_skills)
    WHERE is_deleted = FALSE;

-- Detail table: all_skills
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_detail_all_skills_gin
    ON profiles_detail USING GIN(all_skills);

-- JSONB indexes for experience/education (optional)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_detail_experience_gin
    ON profiles_detail USING GIN(experience_json);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_detail_education_gin
    ON profiles_detail USING GIN(education_json);

-- =============================================================================
-- TRIGRAM INDEXES (Fuzzy Text Search)
-- =============================================================================

-- Full name (fuzzy matching)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hot_name_trgm
    ON profiles_hot USING GIN(full_name gin_trgm_ops)
    WHERE is_deleted = FALSE;

-- Job title (fuzzy matching)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hot_job_title_trgm
    ON profiles_hot USING GIN(job_title gin_trgm_ops)
    WHERE is_deleted = FALSE;

-- Company name (fuzzy matching)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hot_company_trgm
    ON profiles_hot USING GIN(company_name gin_trgm_ops)
    WHERE is_deleted = FALSE;

-- =============================================================================
-- HNSW VECTOR INDEX (Build LAST!)
-- =============================================================================

-- M2-optimized HNSW parameters:
-- - m=16: Balanced recall/speed (default is 16)
-- - ef_construction=200: Higher = better recall during build (default 64)
-- - Query-time tuning: SET hnsw.ef_search = 100 (default 40)

-- IMPORTANT: This index is EXPENSIVE to build
-- Estimated time: 30-60 minutes for 5M profiles
-- Memory usage: ~2-4GB during build

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hot_embedding_hnsw
    ON profiles_hot
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200)
    WHERE embedding IS NOT NULL AND is_deleted = FALSE;

-- Alternative: IVFFlat index (faster build, slower queries)
-- CREATE INDEX CONCURRENTLY idx_hot_embedding_ivfflat
--     ON profiles_hot
--     USING ivfflat (embedding vector_cosine_ops)
--     WITH (lists = 1000)
--     WHERE embedding IS NOT NULL AND is_deleted = FALSE;

-- =============================================================================
-- UTILITY INDEXES
-- =============================================================================

-- LinkedIn username (unique lookup)
-- Already covered by UNIQUE constraint, but explicit index helps
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hot_linkedin_username
    ON profiles_hot(linkedin_username)
    WHERE is_deleted = FALSE;

-- Content hash (deduplication)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hot_content_hash
    ON profiles_hot(content_hash)
    WHERE is_deleted = FALSE;

-- Updated timestamp (for incremental processing)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hot_updated_at
    ON profiles_hot(updated_at DESC)
    WHERE is_deleted = FALSE;

-- Embedding checkpoint (batch resume)
CREATE INDEX IF NOT EXISTS idx_checkpoint_batch_name
    ON embedding_checkpoint(batch_name);

-- =============================================================================
-- VERIFY INDEXES
-- =============================================================================

SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) AS size
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('profiles_hot', 'profiles_detail')
ORDER BY tablename, indexname;

-- =============================================================================
-- QUERY-TIME TUNING
-- =============================================================================

-- For HNSW queries, set higher ef_search for better recall:
-- SET hnsw.ef_search = 100;  -- Higher = better recall (default 40)
-- SET hnsw.ef_search = 200;  -- Even better recall (slower)

-- Example query with HNSW:
-- SET hnsw.ef_search = 100;
-- SELECT id, full_name, job_title,
--        (1 - (embedding <=> $1::vector)) as similarity
-- FROM profiles_hot
-- WHERE is_deleted = FALSE
--   AND location_country = 'United States'
-- ORDER BY embedding <=> $1::vector
-- LIMIT 20;
