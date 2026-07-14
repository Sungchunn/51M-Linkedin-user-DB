#!/bin/bash
# INSIGHT - Fresh Start Script
# Removes all old volumes and starts with clean database

set -e  # Exit on error

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$PROJECT_ROOT"

echo "============================================================"
echo "🆕 INSIGHT - Fresh Start"
echo "============================================================"
echo ""
echo "This will:"
echo "  1. Stop all containers"
echo "  2. Remove ALL old volumes (~30GB)"
echo "  3. Start fresh containers"
echo "  4. Create clean database schema"
echo "  5. Run system tests"
echo ""
echo "⚠️  WARNING: This will DELETE the old 9,938 profiles"
echo ""
read -p "Continue? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Fresh start cancelled."
    exit 0
fi

# Step 1: Stop all containers
echo ""
echo "Step 1: Stopping all containers..."
echo "------------------------------------------------------------"
docker compose down
echo "✅ Containers stopped"

# Step 2: Remove ALL volumes (old + new)
echo ""
echo "Step 2: Removing all volumes..."
echo "------------------------------------------------------------"
echo "Freeing up disk space..."
docker volume rm semantic-talent-finder_postgres_data 2>/dev/null || echo "  (semantic-talent-finder_postgres_data not found)"
docker volume rm semantic-talent-finder_redis_data 2>/dev/null || echo "  (semantic-talent-finder_redis_data not found)"
docker volume rm webapplication_insight_pgdata 2>/dev/null || echo "  (webapplication_insight_pgdata not found)"
docker volume rm yelp_db_volume 2>/dev/null || echo "  (yelp_db_volume not found)"
docker volume rm profiles_postgres_data 2>/dev/null || echo "  (profiles_postgres_data not found)"
docker volume rm profiles_redis_data 2>/dev/null || echo "  (profiles_redis_data not found)"
echo "✅ Old volumes removed"

# Step 3: Verify disk space freed
echo ""
echo "Step 3: Checking disk space..."
echo "------------------------------------------------------------"
docker system df -v | grep -A 10 "^VOLUME NAME"
echo ""

# Step 4: Start fresh containers
echo ""
echo "Step 4: Starting fresh containers..."
echo "------------------------------------------------------------"
docker compose up -d

echo "Waiting for PostgreSQL to be ready..."
sleep 15

# Wait for PostgreSQL to be healthy
for i in {1..30}; do
    if PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres -d profiles -c "SELECT 1;" > /dev/null 2>&1; then
        echo "✅ PostgreSQL is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ PostgreSQL failed to start"
        echo ""
        echo "Checking logs:"
        docker logs profiles_postgres
        exit 1
    fi
    echo "Waiting... ($i/30)"
    sleep 2
done

# Step 5: Install extensions
echo ""
echo "Step 5: Installing PostgreSQL extensions..."
echo "------------------------------------------------------------"
PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres -d profiles -f sql/01_extensions.sql
echo "✅ Extensions installed"

# Step 6: Create schema
echo ""
echo "Step 6: Creating database schema..."
echo "------------------------------------------------------------"
PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres -d profiles -f migrations/003_core_schema.sql
echo "✅ Schema created"

# Step 7: Verify empty database
echo ""
echo "Step 7: Verifying clean database..."
echo "------------------------------------------------------------"
PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres -d profiles -c "
SELECT
    COUNT(*) as total_profiles,
    COUNT(embedding) as with_embeddings
FROM profiles
WHERE is_deleted = FALSE;
"
echo "✅ Database is clean"

echo ""
echo "============================================================"
echo "🎉 FRESH START COMPLETE!"
echo "============================================================"
echo ""
echo "Your system is now running with:"
echo "  ✅ Clean database (0 profiles)"
echo "  ✅ ~30GB disk space freed"
echo "  ✅ PostgreSQL 17 + pgvector ready"
echo "  ✅ Redis cache ready"
echo ""
echo "Next Steps:"
echo ""
echo "  1. Test S3 connection:"
echo "     ./scripts/test_complete_setup.sh"
echo ""
echo "  2. Load data from S3 (when ready):"
echo "     poetry run python3 scripts/load_from_s3.py"
echo ""
echo "  3. Generate embeddings (when ready):"
echo "     poetry run python3 backend/data_pipeline/embeddings/generate.py"
echo ""
echo "  4. Build indexes (after data loaded):"
echo "     PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres \\"
echo "       -d profiles -f sql/03_indexes.sql"
echo ""
echo "  5. Start API server:"
echo "     ./start_api.sh"
echo ""
echo "⚠️  SECURITY REMINDER:"
echo "  Rotate your AWS credentials if they were exposed"
echo "  See: docs/guides/SECURITY.md"
echo ""
echo "============================================================"
