#!/bin/bash
# INSIGHT - Complete System Test Script
# Tests: Configuration, Docker, PostgreSQL, S3 Connection

# Get script directory and project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Change to project root
cd "$PROJECT_ROOT"

echo "============================================================"
echo "🔍 INSIGHT - Complete System Test"
echo "============================================================"
echo ""

# Step 1: Verify Configuration
echo "Step 1: Verifying Configuration..."
echo "------------------------------------------------------------"
poetry run python3 << 'VERIFY_CONFIG'
import os
from dotenv import load_dotenv

# Load .env from current directory
load_dotenv('.env')

print("\n📋 Configuration Status:\n")

key = os.getenv('AWS_ACCESS_KEY_ID')
secret = os.getenv('AWS_SECRET_ACCESS_KEY')
region = os.getenv('AWS_REGION')
s3_path = os.getenv('PARQUET_S3_PATH')

errors = []

if key and key.startswith('AKIA') and len(key) == 20:
    print(f"  ✅ Access Key: {key[:10]}...{key[-4:]}")
else:
    print(f"  ❌ Access Key: Invalid or not set")
    errors.append("AWS_ACCESS_KEY_ID")

if secret and len(secret) == 40:
    print(f"  ✅ Secret Key: {secret[:5]}...{secret[-4:]}")
else:
    print(f"  ❌ Secret Key: Invalid or not set")
    errors.append("AWS_SECRET_ACCESS_KEY")

print(f"  ✅ Region: {region}")
print(f"  ✅ S3 Path: {s3_path}")

if errors:
    print(f"\n❌ Configuration errors: {', '.join(errors)}")
    print("\nPlease update .env with valid credentials.")
    exit(1)
else:
    print("\n✅ Configuration valid!")
VERIFY_CONFIG

echo ""

# Step 2: Check Docker Containers
echo "Step 2: Testing Docker Containers..."
echo "------------------------------------------------------------"
docker compose ps
echo ""

# Step 3: Test PostgreSQL
echo "Step 3: Testing PostgreSQL Connection..."
echo "------------------------------------------------------------"
PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres -d profiles -c "SELECT version();" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ PostgreSQL connected"
else
    echo "❌ PostgreSQL connection failed"
    echo "Run: docker compose up -d"
    exit 1
fi
echo ""

# Step 4: Check Existing Data
echo "Step 4: Checking Existing Data..."
echo "------------------------------------------------------------"
PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres -d profiles -c "
SELECT
    COUNT(*) as total_profiles,
    COUNT(embedding) as with_embeddings,
    ROUND(AVG(content_quality_score)::numeric, 2) as avg_quality
FROM profiles
WHERE is_deleted = FALSE;
"
echo ""

# Step 5: Test S3 Connection
echo "Step 5: Testing S3 Connection (DuckDB)..."
echo "------------------------------------------------------------"
poetry run python3 << 'TEST_S3'
import os
import asyncio
from dotenv import load_dotenv

# Load .env from current directory
load_dotenv('.env')

from backend.duck import get_duckdb_conn, get_parquet_path

async def test():
    print("\n🔗 Connecting to S3 Access Point...\n")
    print(f"  Path: {get_parquet_path()}")
    print(f"  Region: {os.getenv('AWS_REGION')}\n")

    try:
        conn = get_duckdb_conn()

        # Test 1: Count rows
        print("  Test 1: Counting rows...")
        query = f"SELECT COUNT(*) as total FROM read_parquet('{get_parquet_path()}');"
        result = conn.execute(query).fetchone()
        total = result[0]
        print(f"  ✅ Total rows: {total:,}\n")

        # Test 2: Sample data
        print("  Test 2: Fetching sample data...")
        sample_query = f"SELECT * FROM read_parquet('{get_parquet_path()}') LIMIT 3;"
        sample = conn.execute(sample_query).fetchall()
        print(f"  ✅ Sample retrieved: {len(sample)} rows\n")

        # Test 3: Check schema
        print("  Test 3: Verifying schema...")
        schema_query = f"DESCRIBE SELECT * FROM read_parquet('{get_parquet_path()}') LIMIT 0;"
        columns = conn.execute(schema_query).fetchall()
        print(f"  ✅ Columns found: {len(columns)}\n")

        print("="*60)
        print("✅ S3 CONNECTION SUCCESSFUL!")
        print("="*60)
        return True

    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ S3 CONNECTION FAILED\n")
        print(f"Error: {error_msg}\n")

        if "403" in error_msg or "Forbidden" in error_msg:
            print("Troubleshooting (Access Denied):")
            print("  1. Verify IAM user has AmazonS3ReadOnlyAccess")
            print("  2. Check credentials are correct in .env")
            print("  3. Wait 1-2 minutes for AWS propagation")
        elif "401" in error_msg or "Unauthorized" in error_msg:
            print("Troubleshooting (Invalid Credentials):")
            print("  1. Double-check AWS_ACCESS_KEY_ID in .env")
            print("  2. Double-check AWS_SECRET_ACCESS_KEY in .env")
            print("  3. Ensure access key is active (not deactivated)")
        elif "NoSuchKey" in error_msg or "404" in error_msg:
            print("Troubleshooting (File Not Found):")
            print("  1. Verify USA_filtered.parquet exists in access point")
            print("  2. Check PARQUET_S3_PATH in .env")
        else:
            print("Troubleshooting:")
            print("  1. Check internet connection")
            print("  2. Verify AWS region is correct")
            print("  3. Try again in 1-2 minutes")

        return False

result = asyncio.run(test())
exit(0 if result else 1)
TEST_S3

# Final Summary
if [ $? -eq 0 ]; then
    echo ""
    echo "============================================================"
    echo "🎉 ALL TESTS PASSED!"
    echo "============================================================"
    echo ""
    echo "Your system is ready! Next steps:"
    echo ""
    echo "  1. Run migration (preserves existing 5,002 embeddings):"
    echo "     poetry run python3 scripts/migrate_to_hot_schema.py"
    echo ""
    echo "  2. Build indexes (takes 60-90 min):"
    echo "     PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres \\"
    echo "       -d profiles -f sql/03_indexes.sql"
    echo ""
    echo "  3. Start API:"
    echo "     ./start_api.sh"
    echo ""
    echo "============================================================"
    exit 0
else
    echo ""
    echo "============================================================"
    echo "❌ S3 CONNECTION TEST FAILED"
    echo "============================================================"
    echo ""
    echo "Common fixes:"
    echo ""
    echo "  If credentials just rotated:"
    echo "    → Wait 1-2 minutes for AWS propagation, then retry"
    echo ""
    echo "  If access denied:"
    echo "    → Verify IAM user has 'AmazonS3ReadOnlyAccess' policy"
    echo "    → Check credentials in .env are correct"
    echo ""
    echo "  If file not found:"
    echo "    → Verify USA_filtered.parquet exists in S3"
    echo "    → Check PARQUET_S3_PATH in .env"
    echo ""
    echo "To retry: ./scripts/test_complete_setup.sh"
    echo "============================================================"
    exit 1
fi
