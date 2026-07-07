-- INSIGHT - Migration from Existing profiles Table
-- Migrates 10M profiles to new hot/detail schema with hotness scoring

-- IMPORTANT: This migration assumes you have an existing 'profiles' table
-- from Phase 0-4 implementation. If not, skip this file.

-- Estimated time: 10-30 minutes for 10M profiles
-- Memory usage: ~4-8GB during migration

BEGIN;

-- =============================================================================
-- STEP 1: Calculate Hotness Scores
-- =============================================================================

-- Create temporary ranking table with hotness scores
-- Formula: α*quality + β*recency + γ*completeness + δ*engagement

DROP TABLE IF EXISTS hotness_ranked CASCADE;

CREATE TEMP TABLE hotness_ranked AS
SELECT
    id,
    linkedin_username,
    (
        -- α: Quality score (0-50 points)
        COALESCE(content_quality_score, 0) * 50 +

        -- β: Recency (5-30 points)
        CASE
            WHEN updated_at > NOW() - INTERVAL '30 days' THEN 30
            WHEN updated_at > NOW() - INTERVAL '90 days' THEN 15
            ELSE 5
        END +

        -- γ: Completeness (0-20 points)
        CASE
            WHEN skills IS NOT NULL AND array_length(skills, 1) >= 10 THEN 20
            WHEN skills IS NOT NULL AND array_length(skills, 1) >= 5 THEN 10
            ELSE 0
        END +

        -- δ: Engagement (0 for initial migration)
        0
    ) AS hotness_score,
    ROW_NUMBER() OVER (
        ORDER BY
            content_quality_score DESC NULLS LAST,
            updated_at DESC,
            array_length(skills, 1) DESC NULLS LAST
    ) AS rank
FROM profiles
WHERE is_deleted = FALSE
  AND content_quality_score >= 0.5;

-- Create index for fast lookups
CREATE INDEX idx_hotness_rank ON hotness_ranked(rank);
CREATE INDEX idx_hotness_id ON hotness_ranked(id);

-- =============================================================================
-- STEP 2: Backfill profiles_hot (Narrow Serving Table)
-- =============================================================================

-- Option A: Migrate ALL profiles (10M)
-- Option B: Migrate TOP 5M only (uncomment WHERE clause at bottom)

INSERT INTO profiles_hot (
    id,
    linkedin_username,
    full_name,
    job_title,
    company_name,
    headline,
    location_country,
    industry,
    seniority_level,
    years_experience,
    top_skills,
    embedding,
    embedding_generated_at,
    content_hash,
    quality_score,
    hotness_score,
    query_count_7d,
    click_count_7d,
    created_at,
    updated_at,
    last_promoted_at,
    is_deleted
)
SELECT
    p.id,
    p.linkedin_username,
    p.full_name,
    p.job_title,
    p.company_name,
    LEFT(p.headline, 500) AS headline,              -- Truncate to 500 chars
    p.location_country,
    p.industry,
    -- Derive seniority from job title (simple heuristic)
    CASE
        WHEN LOWER(p.job_title) ~ '(vp|vice president|cxo|chief|director)' THEN 'executive'
        WHEN LOWER(p.job_title) ~ '(senior|sr\.|lead|principal|staff)' THEN 'senior'
        WHEN LOWER(p.job_title) ~ '(junior|jr\.|associate|entry)' THEN 'junior'
        ELSE 'mid-level'
    END AS seniority_level,
    p.years_experience,
    p.skills[1:10] AS top_skills,                   -- Top 10 skills only

    -- Convert 1536-d to 384-d (PLACEHOLDER - requires re-embedding)
    -- For now, set to NULL (will be populated by embedding pipeline)
    NULL::vector(384) AS embedding,
    NULL AS embedding_generated_at,

    -- Content hash for deduplication
    MD5(
        LOWER(COALESCE(p.full_name, '')) || '|' ||
        LOWER(COALESCE(p.job_title, '')) || '|' ||
        LOWER(COALESCE(p.company_name, ''))
    ) AS content_hash,

    p.content_quality_score AS quality_score,
    COALESCE(hr.hotness_score, 0) AS hotness_score,
    0 AS query_count_7d,
    0 AS click_count_7d,
    p.created_at,
    p.updated_at,
    NOW() AS last_promoted_at,
    FALSE AS is_deleted
FROM profiles p
LEFT JOIN hotness_ranked hr ON p.id = hr.id
WHERE p.is_deleted = FALSE
  AND p.content_quality_score >= 0.5

-- OPTION B: Uncomment to limit to top 5M profiles
-- AND hr.rank IS NOT NULL
-- AND hr.rank <= 5000000

ON CONFLICT (linkedin_username) DO NOTHING;

-- =============================================================================
-- STEP 3: Backfill profiles_detail (Long Fields)
-- =============================================================================

INSERT INTO profiles_detail (
    id,
    summary,
    experience_json,
    education_json,
    certifications_json,
    email,
    phone,
    website,
    twitter,
    github,
    all_skills,
    profile_completeness,
    linkedin_url,
    created_at,
    updated_at
)
SELECT
    p.id,
    p.summary,

    -- Convert work history to JSONB (if structured data available)
    -- PLACEHOLDER: Adjust based on your schema
    NULL::JSONB AS experience_json,
    NULL::JSONB AS education_json,
    NULL::JSONB AS certifications_json,

    p.email,
    p.phone,
    p.website,
    p.twitter,
    p.github,
    p.skills AS all_skills,
    p.profile_completeness,
    p.linkedin_url,
    p.created_at,
    p.updated_at
FROM profiles p
WHERE EXISTS (
    SELECT 1 FROM profiles_hot h WHERE h.id = p.id
)
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- STEP 4: Verification
-- =============================================================================

-- Check migration stats
SELECT
    'profiles_hot' AS table_name,
    COUNT(*) AS total_rows,
    COUNT(embedding) AS with_embeddings,
    ROUND(AVG(quality_score)::numeric, 2) AS avg_quality,
    ROUND(AVG(hotness_score)::numeric, 2) AS avg_hotness
FROM profiles_hot
UNION ALL
SELECT
    'profiles_detail' AS table_name,
    COUNT(*) AS total_rows,
    NULL AS with_embeddings,
    NULL AS avg_quality,
    NULL AS avg_hotness
FROM profiles_detail;

-- Check hotness distribution
SELECT
    CASE
        WHEN hotness_score >= 80 THEN '80-100 (hot)'
        WHEN hotness_score >= 60 THEN '60-80 (warm)'
        WHEN hotness_score >= 40 THEN '40-60 (medium)'
        ELSE '0-40 (cold)'
    END AS hotness_range,
    COUNT(*) AS count,
    ROUND(AVG(quality_score)::numeric, 2) AS avg_quality
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

-- Check table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    pg_total_relation_size(schemaname||'.'||tablename) AS bytes
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN ('profiles', 'profiles_hot', 'profiles_detail')
ORDER BY bytes DESC;

COMMIT;

-- =============================================================================
-- POST-MIGRATION NOTES
-- =============================================================================

-- 1. Embeddings are NULL after migration (384-d vs 1536-d)
--    Run embedding pipeline: make embed/openai (or make embed/mps)

-- 2. Build indexes AFTER migration (faster)
--    Run: psql -U postgres -d profiles -f sql/03_indexes.sql

-- 3. Optional: Drop old profiles table to save disk space
--    DROP TABLE profiles CASCADE;

-- 4. Vacuum and analyze
--    VACUUM ANALYZE profiles_hot;
--    VACUUM ANALYZE profiles_detail;
