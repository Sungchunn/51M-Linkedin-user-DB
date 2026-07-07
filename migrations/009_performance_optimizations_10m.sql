-- ================================================
-- PROSPECTIQ - Performance Optimizations for 10M+ Profiles
-- Run this after loading 10M+ profiles
-- ================================================

-- ================================================
-- 1. PARTITIONING BY REGION (US States)
-- ================================================

-- Note: Partitioning requires recreating the table
-- Run this BEFORE loading 10M+ data for best results

/*
-- Create partitioned table (uncomment when ready)
CREATE TABLE profiles_partitioned (
    LIKE profiles INCLUDING DEFAULTS INCLUDING CONSTRAINTS
) PARTITION BY LIST (region);

-- Create partition for each major state (top 20 by volume)
CREATE TABLE profiles_california PARTITION OF profiles_partitioned FOR VALUES IN ('california');
CREATE TABLE profiles_texas PARTITION OF profiles_partitioned FOR VALUES IN ('texas');
CREATE TABLE profiles_florida PARTITION OF profiles_partitioned FOR VALUES IN ('florida');
CREATE TABLE profiles_new_york PARTITION OF profiles_partitioned FOR VALUES IN ('new york');
CREATE TABLE profiles_illinois PARTITION OF profiles_partitioned FOR VALUES IN ('illinois');
CREATE TABLE profiles_pennsylvania PARTITION OF profiles_partitioned FOR VALUES IN ('pennsylvania');
CREATE TABLE profiles_ohio PARTITION OF profiles_partitioned FOR VALUES IN ('ohio');
CREATE TABLE profiles_georgia PARTITION OF profiles_partitioned FOR VALUES IN ('georgia');
CREATE TABLE profiles_north_carolina PARTITION OF profiles_partitioned FOR VALUES IN ('north carolina');
CREATE TABLE profiles_michigan PARTITION OF profiles_partitioned FOR VALUES IN ('michigan');

-- Default partition for all other states
CREATE TABLE profiles_other_states PARTITION OF profiles_partitioned DEFAULT;

-- Migrate data (run during low-traffic period)
INSERT INTO profiles_partitioned SELECT * FROM profiles;

-- Rename tables
ALTER TABLE profiles RENAME TO profiles_old;
ALTER TABLE profiles_partitioned RENAME TO profiles;

-- Drop old table after verification
-- DROP TABLE profiles_old;
*/

-- ================================================
-- 2. COMPOSITE INDEXES FOR COMMON QUERIES
-- ================================================

-- Index for "software engineers in California with 5+ years"
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_industry_region_exp
    ON profiles (industry, region, years_experience)
    WHERE quality_score > 60;

-- Index for job title + location searches
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_title_region
    ON profiles (job_title, region)
    WHERE quality_score > 60;

-- Index for company searches
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_company
    ON profiles (company_name)
    WHERE quality_score > 60;

-- ================================================
-- 3. PARTIAL INDEXES (High-Quality Profiles Only)
-- ================================================

-- Most searches will be on high-quality profiles (80%+ of traffic)
-- Partial indexes are smaller and faster

-- High-quality profiles index (quality > 70)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_high_quality
    ON profiles (quality_score DESC, years_experience)
    WHERE quality_score > 70;

-- Premium profiles index (quality > 80)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_premium
    ON profiles (quality_score DESC, industry, region)
    WHERE quality_score > 80;

-- ================================================
-- 4. GIN INDEXES FOR ARRAY SEARCHES
-- ================================================

-- Skills array search (already exists, but ensure it's there)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_skills_gin
    ON profiles USING GIN (skills);

-- Add trigram index for fuzzy name matching
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_fullname_trgm
    ON profiles USING GIN (full_name gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_company_trgm
    ON profiles USING GIN (company_name gin_trgm_ops);

-- ================================================
-- 5. MATERIALIZED VIEWS FOR POPULAR SEARCHES
-- ================================================

-- Software Engineers (most common search)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_software_engineers AS
SELECT * FROM profiles
WHERE industry IN ('computer software', 'information technology and services')
  AND quality_score > 70
ORDER BY quality_score DESC;

CREATE UNIQUE INDEX ON mv_software_engineers (id);
CREATE INDEX ON mv_software_engineers (region);
CREATE INDEX ON mv_software_engineers (years_experience);

-- Marketing Professionals
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_marketing_pros AS
SELECT * FROM profiles
WHERE industry IN ('marketing and advertising', 'marketing')
  AND quality_score > 70
ORDER BY quality_score DESC;

CREATE UNIQUE INDEX ON mv_marketing_pros (id);
CREATE INDEX ON mv_marketing_pros (region);

-- Sales Leaders
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_sales_leaders AS
SELECT * FROM profiles
WHERE (job_title ILIKE '%sales%' OR industry = 'sales')
  AND quality_score > 70
ORDER BY quality_score DESC;

CREATE UNIQUE INDEX ON mv_sales_leaders (id);
CREATE INDEX ON mv_sales_leaders (region);

-- Refresh schedule: Run these commands nightly via cron/scheduler
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_software_engineers;
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_marketing_pros;
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_sales_leaders;

-- ================================================
-- 6. STATISTICS AND QUERY PLANNER OPTIMIZATION
-- ================================================

-- Update statistics for better query planning
ANALYZE profiles;

-- Set statistics target higher for frequently queried columns
ALTER TABLE profiles ALTER COLUMN quality_score SET STATISTICS 1000;
ALTER TABLE profiles ALTER COLUMN industry SET STATISTICS 1000;
ALTER TABLE profiles ALTER COLUMN region SET STATISTICS 1000;
ALTER TABLE profiles ALTER COLUMN job_title SET STATISTICS 1000;

-- Re-analyze with new statistics settings
ANALYZE profiles;

-- ================================================
-- 7. VACUUM AND MAINTENANCE
-- ================================================

-- Full vacuum (run during low-traffic period)
-- VACUUM FULL ANALYZE profiles;

-- Regular vacuum
VACUUM ANALYZE profiles;

-- ================================================
-- 8. CONNECTION POOLING SETTINGS
-- ================================================

-- These are set at database level, not in SQL
-- Add to postgresql.conf or set via cloud provider:

-- max_connections = 200
-- shared_buffers = 8GB (25% of RAM for 32GB)
-- effective_cache_size = 24GB (75% of RAM)
-- maintenance_work_mem = 2GB
-- checkpoint_completion_target = 0.9
-- wal_buffers = 16MB
-- default_statistics_target = 500
-- random_page_cost = 1.1
-- effective_io_concurrency = 200
-- work_mem = 20MB
-- min_wal_size = 2GB
-- max_wal_size = 8GB
-- max_worker_processes = 8
-- max_parallel_workers_per_gather = 4
-- max_parallel_workers = 8
-- max_parallel_maintenance_workers = 4

-- ================================================
-- 9. CREATE HELPER FUNCTIONS
-- ================================================

-- Function to get profile counts by region
CREATE OR REPLACE FUNCTION get_region_stats()
RETURNS TABLE (
    region_name TEXT,
    profile_count BIGINT,
    avg_quality_score NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        region,
        COUNT(*),
        ROUND(AVG(quality_score), 2)
    FROM profiles
    WHERE quality_score > 60
    GROUP BY region
    ORDER BY COUNT(*) DESC
    LIMIT 50;
END;
$$ LANGUAGE plpgsql;

-- Function to get industry stats
CREATE OR REPLACE FUNCTION get_industry_stats()
RETURNS TABLE (
    industry_name TEXT,
    profile_count BIGINT,
    avg_years_exp NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        industry,
        COUNT(*),
        ROUND(AVG(years_experience), 1)
    FROM profiles
    WHERE quality_score > 60
    GROUP BY industry
    ORDER BY COUNT(*) DESC
    LIMIT 50;
END;
$$ LANGUAGE plpgsql;

-- ================================================
-- 10. MONITORING VIEWS
-- ================================================

-- View for monitoring index usage
CREATE OR REPLACE VIEW v_index_usage AS
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched,
    pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;

-- View for monitoring table bloat
CREATE OR REPLACE VIEW v_table_bloat AS
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as index_size,
    n_live_tup as live_tuples,
    n_dead_tup as dead_tuples,
    ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup, 0), 2) as dead_tuple_pct
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- ================================================
-- USAGE EXAMPLES
-- ================================================

-- Check index usage
-- SELECT * FROM v_index_usage;

-- Check table bloat
-- SELECT * FROM v_table_bloat;

-- Get region stats
-- SELECT * FROM get_region_stats();

-- Get industry stats
-- SELECT * FROM get_industry_stats();

-- Refresh materialized views (run nightly)
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_software_engineers;

-- ================================================
-- COMPLETION MESSAGE
-- ================================================

DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '✅ Performance optimizations applied!';
    RAISE NOTICE '';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '1. Run ANALYZE to update statistics';
    RAISE NOTICE '2. Monitor query performance with EXPLAIN ANALYZE';
    RAISE NOTICE '3. Refresh materialized views nightly';
    RAISE NOTICE '4. Check index usage: SELECT * FROM v_index_usage;';
    RAISE NOTICE '';
END $$;
