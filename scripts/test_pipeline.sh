#!/bin/bash
# INSIGHT - Test Data Pipeline with Single Batch
# Tests: Parquet → Staging → Core transformation

set -e  # Exit on error

echo "================================================"
echo "INSIGHT - Phase 2 Pipeline Test"
echo "Testing with batch_0000.parquet"
echo "================================================"
echo ""

# Step 1: Reset database
echo "Step 1: Resetting database..."
echo "⚠️  You will be prompted to type 'DELETE' to confirm"
echo ""
poetry run reset-db --force  # Use --force to skip confirmation

echo ""
echo "================================================"
echo "Step 2: Loading Parquet to staging..."
echo "================================================"
poetry run load-parquet "/Users/chromatrical/CAREER/Side Projects/51M-Linkedin-user-DB/data/batches/batch_0000.parquet"

echo ""
echo "================================================"
echo "Step 3: Transforming staging → core..."
echo "================================================"
poetry run load-core

echo ""
echo "================================================"
echo "Step 4: Verification queries"
echo "================================================"

# Connect to PostgreSQL and run verification queries
psql "host=localhost port=5433 dbname=semantic_talent user=postgres password=postgres" <<EOF
-- Staging table count
\echo '--- Staging Table Count ---'
SELECT count(*) as staging_rows FROM staging_profiles_raw;

\echo ''
\echo '--- Core Profiles Count ---'
SELECT count(*) as core_profiles FROM profiles;

\echo ''
\echo '--- Sample Profile ---'
SELECT
    full_name,
    linkedin_username,
    job_title,
    company_name,
    location_country,
    content_quality_score
FROM profiles
LIMIT 3;

\echo ''
\echo '--- Quality Score Distribution ---'
SELECT
    CASE
        WHEN content_quality_score >= 0.9 THEN '0.9-1.0 (Excellent)'
        WHEN content_quality_score >= 0.7 THEN '0.7-0.9 (Good)'
        WHEN content_quality_score >= 0.5 THEN '0.5-0.7 (Fair)'
        ELSE '<0.5 (Poor)'
    END as quality_range,
    count(*) as profile_count
FROM profiles
GROUP BY
    CASE
        WHEN content_quality_score >= 0.9 THEN '0.9-1.0 (Excellent)'
        WHEN content_quality_score >= 0.7 THEN '0.7-0.9 (Good)'
        WHEN content_quality_score >= 0.5 THEN '0.5-0.7 (Fair)'
        ELSE '<0.5 (Poor)'
    END
ORDER BY quality_range DESC;

\echo ''
\echo '--- Skills Array Sample ---'
SELECT
    full_name,
    array_length(skills, 1) as skill_count,
    skills
FROM profiles
WHERE skills IS NOT NULL
LIMIT 3;

EOF

echo ""
echo "================================================"
echo "✅ Pipeline test complete!"
echo "================================================"
