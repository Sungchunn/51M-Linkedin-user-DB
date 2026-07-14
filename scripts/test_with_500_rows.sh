#!/bin/bash
# Test pipeline with 500-row test file

set -e  # Exit on error

# Change to project directory
cd "/Users/chromatrical/CAREER/Side Projects/51M-Linkedin-user-DB"

echo "================================================"
echo "INSIGHT - Pipeline Test (500 rows)"
echo "================================================"
echo ""

# Step 1: Reset database
echo "Step 1: Resetting database..."
poetry run reset-db --force

echo ""
echo "================================================"
echo "Step 2: Loading test_500_rows.parquet..."
echo "================================================"
poetry run load-parquet "/Users/chromatrical/CAREER/Side Projects/51M-Linkedin-user-DB/data/test_500_rows.parquet"

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
    (SELECT count(*) FROM profiles) as core_profiles;

\echo ''
\echo '--- Sample Profiles ---'
SELECT
    full_name,
    job_title,
    company_name,
    location_country,
    content_quality_score
FROM profiles
LIMIT 5;

\echo ''
\echo '--- Quality Score Distribution ---'
SELECT
    CASE
        WHEN content_quality_score >= 0.9 THEN '0.9-1.0'
        WHEN content_quality_score >= 0.7 THEN '0.7-0.9'
        WHEN content_quality_score >= 0.5 THEN '0.5-0.7'
        ELSE '<0.5'
    END as quality_range,
    count(*) as count
FROM profiles
GROUP BY 1
ORDER BY 1 DESC;

EOF

echo ""
echo "================================================"
echo "✅ Test complete!"
echo "================================================"
