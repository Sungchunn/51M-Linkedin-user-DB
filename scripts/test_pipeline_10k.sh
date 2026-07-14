#!/bin/bash
# Test pipeline with 10,000 rows

set -e  # Exit on error

cd "/Users/chromatrical/CAREER/Side Projects/51M-Linkedin-user-DB"

echo "================================================"
echo "INSIGHT - Pipeline Test (10,000 rows)"
echo "================================================"
echo ""

# Step 1: Reset database
echo "Step 1: Resetting database..."
poetry run reset-db --force

echo ""
echo "================================================"
echo "Step 2: Loading test_10000_rows.parquet..."
echo "================================================"
poetry run load-parquet "/Users/chromatrical/CAREER/Side Projects/51M-Linkedin-user-DB/data/test_10000_rows.parquet"

echo ""
echo "================================================"
echo "Step 3: Transforming staging → core..."
echo "================================================"
poetry run load-core

echo ""
echo "================================================"
echo "Step 4: Verification"
echo "================================================"

psql "host=localhost port=5433 dbname=semantic_talent user=postgres password=postgres" <<EOF
-- Row counts
\echo '--- Row Counts ---'
SELECT
    (SELECT count(*) FROM staging_profiles_raw) as staging_rows,
    (SELECT count(*) FROM profiles) as core_profiles,
    (SELECT count(*) FROM profiles WHERE embedding IS NOT NULL) as profiles_with_embeddings;

\echo ''
\echo '--- Sample Profiles ---'
SELECT
    full_name,
    job_title,
    company_name,
    location_country,
    array_length(skills, 1) as skill_count,
    content_quality_score
FROM profiles
LIMIT 10;

\echo ''
\echo '--- Quality Score Distribution ---'
SELECT
    CASE
        WHEN content_quality_score >= 0.9 THEN '0.9-1.0 (Excellent)'
        WHEN content_quality_score >= 0.7 THEN '0.7-0.9 (Good)'
        WHEN content_quality_score >= 0.5 THEN '0.5-0.7 (Fair)'
        ELSE '<0.5 (Poor)'
    END as quality_range,
    count(*) as count,
    round(count(*) * 100.0 / sum(count(*)) over(), 2) as percentage
FROM profiles
GROUP BY 1
ORDER BY 1 DESC;

\echo ''
\echo '--- Top 10 Skills ---'
SELECT
    unnest(skills) as skill,
    count(*) as profile_count
FROM profiles
WHERE skills IS NOT NULL
GROUP BY 1
ORDER BY 2 DESC
LIMIT 10;

\echo ''
\echo '--- Location Distribution (Top 10) ---'
SELECT
    location_country,
    region,
    count(*) as profile_count
FROM profiles
WHERE location_country IS NOT NULL
GROUP BY 1, 2
ORDER BY 3 DESC
LIMIT 10;

EOF

echo ""
echo "================================================"
echo "✅ Test complete!"
echo "================================================"
