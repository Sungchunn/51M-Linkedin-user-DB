-- INSIGHT - Maintenance Scripts
-- Regular maintenance for optimal performance

-- =============================================================================
-- WEEKLY MAINTENANCE
-- =============================================================================

-- 1. VACUUM ANALYZE (reclaim space, update statistics)
VACUUM ANALYZE profiles_hot;
VACUUM ANALYZE profiles_detail;
VACUUM ANALYZE hot_audit;
VACUUM ANALYZE embedding_checkpoint;

-- 2. Reset weekly counters (query/click counts)
UPDATE profiles_hot
SET query_count_7d = 0,
    click_count_7d = 0
WHERE query_count_7d > 0 OR click_count_7d > 0;

-- =============================================================================
-- MONTHLY MAINTENANCE
-- =============================================================================

-- 1. Aggressive vacuum (full table rewrite - use during low traffic)
-- WARNING: Takes exclusive lock, blocks queries
-- VACUUM FULL ANALYZE profiles_hot;
-- VACUUM FULL ANALYZE profiles_detail;

-- 2. Reindex (rebuild bloated indexes)
REINDEX INDEX CONCURRENTLY idx_hot_embedding_hnsw;
REINDEX INDEX CONCURRENTLY idx_hot_skills_gin;
REINDEX INDEX CONCURRENTLY idx_hot_name_trgm;

-- 3. Archive old audit logs (keep 90 days)
DELETE FROM hot_audit
WHERE performed_at < NOW() - INTERVAL '90 days';

-- =============================================================================
-- QUARTERLY MAINTENANCE
-- =============================================================================

-- 1. Recalculate hotness scores
UPDATE profiles_hot
SET hotness_score = (
    COALESCE(quality_score, 0) * 50 +
    CASE
        WHEN updated_at > NOW() - INTERVAL '30 days' THEN 30
        WHEN updated_at > NOW() - INTERVAL '90 days' THEN 15
        ELSE 5
    END +
    CASE
        WHEN top_skills IS NOT NULL AND array_length(top_skills, 1) >= 10 THEN 20
        WHEN top_skills IS NOT NULL AND array_length(top_skills, 1) >= 5 THEN 10
        ELSE 0
    END +
    COALESCE(query_count_7d, 0) + COALESCE(click_count_7d, 0) * 2
),
last_promoted_at = NOW()
WHERE is_deleted = FALSE;

-- 2. Clean up soft-deleted profiles (optional)
-- DELETE FROM profiles_hot WHERE is_deleted = TRUE AND updated_at < NOW() - INTERVAL '180 days';

-- =============================================================================
-- MONITORING QUERIES
-- =============================================================================

-- 1. Check table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS index_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- 2. Check index bloat
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) AS index_size
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY pg_relation_size(indexname::regclass) DESC
LIMIT 20;

-- 3. Check dead tuples (indicates need for VACUUM)
SELECT
    schemaname,
    relname,
    n_dead_tup,
    n_live_tup,
    ROUND(n_dead_tup::numeric / NULLIF(n_live_tup, 0), 3) AS dead_ratio,
    last_vacuum,
    last_autovacuum
FROM pg_stat_user_tables
WHERE schemaname = 'public'
  AND n_dead_tup > 0
ORDER BY n_dead_tup DESC;

-- 4. Check embedding coverage
SELECT
    COUNT(*) AS total_profiles,
    COUNT(embedding) AS with_embeddings,
    COUNT(*) - COUNT(embedding) AS missing_embeddings,
    ROUND(COUNT(embedding)::numeric / COUNT(*) * 100, 2) AS embedding_pct
FROM profiles_hot
WHERE is_deleted = FALSE;

-- 5. Check hotness distribution
SELECT
    CASE
        WHEN hotness_score >= 80 THEN '80-100 (hot)'
        WHEN hotness_score >= 60 THEN '60-80 (warm)'
        WHEN hotness_score >= 40 THEN '40-60 (medium)'
        ELSE '0-40 (cold)'
    END AS hotness_range,
    COUNT(*) AS count,
    ROUND(AVG(quality_score)::numeric, 2) AS avg_quality,
    ROUND(AVG(query_count_7d)::numeric, 2) AS avg_queries,
    ROUND(AVG(click_count_7d)::numeric, 2) AS avg_clicks
FROM profiles_hot
WHERE is_deleted = FALSE
GROUP BY
    CASE
        WHEN hotness_score >= 80 THEN '80-100 (hot)'
        WHEN hotness_score >= 60 THEN '60-80 (warm)'
        WHEN hotness_score >= 40 THEN '40-60 (medium)'
        ELSE '0-40 (cold)'
    END
ORDER BY hotness_range DESC;

-- =============================================================================
-- PERFORMANCE TUNING
-- =============================================================================

-- 1. Increase work_mem for specific query (session-level)
-- SET work_mem = '256MB';

-- 2. Increase maintenance_work_mem for VACUUM/REINDEX
-- SET maintenance_work_mem = '4GB';

-- 3. Tune HNSW ef_search for better recall
-- SET hnsw.ef_search = 100;  -- Higher = better recall (default 40)

-- 4. Check query plans
-- EXPLAIN (ANALYZE, BUFFERS) SELECT ...;

-- =============================================================================
-- EMERGENCY CLEANUP
-- =============================================================================

-- 1. Kill long-running queries
SELECT
    pid,
    now() - pg_stat_activity.query_start AS duration,
    query,
    state
FROM pg_stat_activity
WHERE state = 'active'
  AND now() - pg_stat_activity.query_start > INTERVAL '5 minutes'
ORDER BY duration DESC;

-- Kill specific query: SELECT pg_terminate_backend(pid);

-- 2. Cancel autovacuum (if blocking critical operations)
-- SELECT pg_cancel_backend(pid) FROM pg_stat_activity WHERE query LIKE 'autovacuum%';

-- 3. Reset connection pool (if pool exhausted)
-- SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'profiles' AND pid <> pg_backend_pid();
