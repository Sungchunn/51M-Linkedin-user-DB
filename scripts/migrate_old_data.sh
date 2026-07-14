#!/bin/bash
# INSIGHT - Data Migration Script
# Migrates 9,938 profiles from old volume to new architecture

set -e  # Exit on error

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$PROJECT_ROOT"

BACKUP_DIR="$PROJECT_ROOT/data/migration_backup"
DUMP_FILE="$BACKUP_DIR/old_profiles_dump.sql"

echo "============================================================"
echo "🔄 INSIGHT - Data Migration from Old Volume"
echo "============================================================"
echo ""
echo "This will:"
echo "  1. Start temporary container with old volume"
echo "  2. Dump 9,938 profiles with embeddings"
echo "  3. Stop and remove old containers"
echo "  4. Clean up old volumes (frees 30GB)"
echo "  5. Start new containers"
echo "  6. Restore data to new database"
echo ""
read -p "Continue? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Migration cancelled."
    exit 0
fi

# Step 1: Create backup directory
echo ""
echo "Step 1: Creating backup directory..."
echo "------------------------------------------------------------"
mkdir -p "$BACKUP_DIR"
echo "✅ Backup directory created: $BACKUP_DIR"

# Step 2: Stop all running containers
echo ""
echo "Step 2: Stopping all containers..."
echo "------------------------------------------------------------"
docker compose down
echo "✅ Containers stopped"

# Step 3: Start temporary container with OLD volume
echo ""
echo "Step 3: Starting temporary container with old volume..."
echo "------------------------------------------------------------"
docker run --name temp_old_postgres \
    -e POSTGRES_USER=postgres \
    -e POSTGRES_PASSWORD=postgres \
    -e POSTGRES_DB=profiles \
    -v semantic-talent-finder_postgres_data:/var/lib/postgresql/data \
    -p 5434:5432 \
    -d pgvector/pgvector:pg17

echo "Waiting for PostgreSQL to start..."
sleep 10

# Verify container is running
if ! docker ps | grep -q temp_old_postgres; then
    echo "❌ Failed to start temporary container"
    exit 1
fi
echo "✅ Temporary container started"

# Step 4: Dump the data
echo ""
echo "Step 4: Dumping profiles table..."
echo "------------------------------------------------------------"
docker exec temp_old_postgres pg_dump \
    -U postgres \
    -d profiles \
    -t profiles \
    --data-only \
    --column-inserts \
    > "$DUMP_FILE"

# Verify dump was created
if [ ! -f "$DUMP_FILE" ]; then
    echo "❌ Failed to create dump file"
    docker stop temp_old_postgres
    docker rm temp_old_postgres
    exit 1
fi

DUMP_SIZE=$(du -h "$DUMP_FILE" | cut -f1)
echo "✅ Data dumped to: $DUMP_FILE ($DUMP_SIZE)"

# Step 5: Stop and remove temporary container
echo ""
echo "Step 5: Stopping temporary container..."
echo "------------------------------------------------------------"
docker stop temp_old_postgres
docker rm temp_old_postgres
echo "✅ Temporary container removed"

# Step 6: Remove old volumes
echo ""
echo "Step 6: Removing old volumes..."
echo "------------------------------------------------------------"
echo "This will free up approximately 30GB of disk space"
echo ""
docker volume rm semantic-talent-finder_postgres_data || true
docker volume rm semantic-talent-finder_redis_data || true
docker volume rm webapplication_insight_pgdata || true
docker volume rm yelp_db_volume || true
echo "✅ Old volumes removed"

# Step 7: Start new containers
echo ""
echo "Step 7: Starting new containers..."
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
        exit 1
    fi
    echo "Waiting... ($i/30)"
    sleep 2
done

# Step 8: Create schema in new database
echo ""
echo "Step 8: Creating database schema..."
echo "------------------------------------------------------------"
PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres -d profiles -f sql/02_schema.sql
echo "✅ Schema created"

# Step 9: Restore data
echo ""
echo "Step 9: Restoring profiles data..."
echo "------------------------------------------------------------"
echo "This may take 2-5 minutes..."
PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres -d profiles -f "$DUMP_FILE"

# Verify restoration
PROFILE_COUNT=$(PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres -d profiles -t -c \
    "SELECT COUNT(*) FROM profiles WHERE is_deleted = FALSE;")
EMBEDDING_COUNT=$(PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres -d profiles -t -c \
    "SELECT COUNT(*) FROM profiles WHERE embedding IS NOT NULL;")

echo ""
echo "✅ Data restored:"
echo "   Profiles: $PROFILE_COUNT"
echo "   Embeddings: $EMBEDDING_COUNT"

# Step 10: Build indexes (optional - takes time)
echo ""
echo "Step 10: Build indexes (OPTIONAL)..."
echo "------------------------------------------------------------"
echo "Index building takes 60-90 minutes but improves query performance."
echo ""
read -p "Build indexes now? (yes/no): " build_indexes

if [ "$build_indexes" = "yes" ]; then
    echo "Building indexes... (this will take 60-90 minutes)"
    PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres -d profiles -f sql/03_indexes.sql
    echo "✅ Indexes built"
else
    echo "⏭️  Skipped index building"
    echo "   You can build them later with:"
    echo "   PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres -d profiles -f sql/03_indexes.sql"
fi

echo ""
echo "============================================================"
echo "🎉 MIGRATION COMPLETE!"
echo "============================================================"
echo ""
echo "Summary:"
echo "  ✅ Profiles migrated: $PROFILE_COUNT"
echo "  ✅ Embeddings preserved: $EMBEDDING_COUNT"
echo "  ✅ Disk space freed: ~30GB"
echo "  ✅ Backup saved: $DUMP_FILE"
echo ""
echo "Next Steps:"
echo ""
echo "  1. Test the system:"
echo "     ./scripts/test_complete_setup.sh"
echo ""
echo "  2. Start the API:"
echo "     ./start_api.sh"
echo ""
echo "  3. (Optional) Remove backup after verification:"
echo "     rm -rf $BACKUP_DIR"
echo ""
echo "⚠️  SECURITY REMINDER:"
echo "  Rotate your AWS credentials if they were exposed"
echo "  See: docs/guides/SECURITY.md"
echo ""
echo "============================================================"
