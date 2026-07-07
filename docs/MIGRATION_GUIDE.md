# INSIGHT - Migration Guide: S3 Integration & Hot/Detail Schema

**Last Updated:** 2025-10-10
**Status:** Ready to execute

---

## 📋 Overview

This guide walks you through:
1. Configuring S3 access for your 51M Parquet dataset
2. Migrating existing 9,938 profiles (with embeddings) to hot/detail schema
3. Loading incremental data from S3
4. Building optimized indexes

---

## ✅ Prerequisites Checklist

- [ ] Docker & Docker Compose installed
- [ ] PostgreSQL container running on port 5432
- [ ] Redis container running on port 6379
- [ ] 51M Parquet file uploaded to S3
- [ ] AWS credentials with S3 read access
- [ ] ~10GB free disk space

---

## 📝 Step-by-Step Instructions

### **Step 1: Update Configuration**

#### **1.1 Update `.env` with S3 Credentials**

Edit `/Users/chromatrical/CAREER/Side Projects/WebApplication/.env`:

```bash
# Replace these with your actual values:
PARQUET_S3_PATH=s3://your-bucket-name/USA_filtered.parquet
AWS_ACCESS_KEY_ID=your-actual-access-key
AWS_SECRET_ACCESS_KEY=your-actual-secret-key
AWS_REGION=us-east-1  # or your bucket region
```

**Verification:**
```bash
# Test S3 access
cd "/Users/chromatrical/CAREER/Side Projects/WebApplication" && \
poetry run python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('S3 Path:', os.getenv('PARQUET_S3_PATH'))
print('Region:', os.getenv('AWS_REGION'))
print('Access Key:', os.getenv('AWS_ACCESS_KEY_ID')[:10] + '...' if os.getenv('AWS_ACCESS_KEY_ID') else 'NOT SET')
"
```

---

### **Step 2: Start Infrastructure**

```bash
cd "/Users/chromatrical/CAREER/Side Projects/WebApplication" && \
docker compose down && \
docker compose up -d && \
sleep 15 && \
docker compose ps
```

**Expected Output:**
```
NAME                 IMAGE                       STATUS
profiles_postgres    pgvector/pgvector:pg17      Up (healthy)
profiles_redis       redis:7-alpine              Up (healthy)
```

**Verify Database Connection:**
```bash
cd "/Users/chromatrical/CAREER/Side Projects/WebApplication" && \
PGPASSWORD=postgres psql -h 127.0.0.1 -p 5432 -U postgres -d profiles -c "SELECT version();"
```

---

### **Step 3: Test DuckDB S3 Connectivity**

```bash
cd "/Users/chromatrical/CAREER/Side Projects/WebApplication" && \
poetry run python3 << 'EOF'
import os
import asyncio
from dotenv import load_dotenv
load_dotenv()

from backend.duck import test_connection, get_parquet_path

async def main():
    print(f"\n📦 Testing S3 connectivity...")
    print(f"Parquet path: {get_parquet_path()}\n")

    success = await test_connection()

    if success:
        print("\n✅ S3 connection successful!")
        print("DuckDB can read your Parquet file from S3")
    else:
        print("\n❌ S3 connection failed")
        print("\nTroubleshooting:")
        print("1. Check AWS_ACCESS_KEY_ID in .env")
        print("2. Check AWS_SECRET_ACCESS_KEY in .env")
        print("3. Verify bucket name and file path")
        print("4. Ensure IAM permissions allow s3:GetObject")

asyncio.run(main())
EOF
```

---

### **Step 4: Analyze Existing Data**

```bash
cd "/Users/chromatrical/CAREER/Side Projects/WebApplication" && \
PGPASSWORD=postgres psql -h 127.0.0.1 -p 5432 -U postgres -d profiles << 'SQL'
-- Check existing data
SELECT
    COUNT(*) as total_profiles,
    COUNT(embedding) as with_embeddings,
    ROUND(AVG(content_quality_score)::numeric, 2) as avg_quality,
    COUNT(CASE WHEN content_quality_score >= 0.7 THEN 1 END) as high_quality
FROM profiles
WHERE is_deleted = FALSE;

-- Sample profile
SELECT
    linkedin_username,
    full_name,
    job_title,
    company_name,
    location_country,
    embedding IS NOT NULL as has_embedding,
    content_quality_score
FROM profiles
WHERE is_deleted = FALSE
LIMIT 5;
SQL
```

**Expected Output:**
```
 total_profiles | with_embeddings | avg_quality | high_quality
----------------+-----------------+-------------+--------------
           9938 |            5002 |        0.85 |         8221
```

---

### **Step 5: Migrate to Hot/Detail Schema**

This preserves your existing embeddings and migrates data to the optimized schema.

```bash
cd "/Users/chromatrical/CAREER/Side Projects/WebApplication" && \
poetry run python3 scripts/migrate_to_hot_schema.py
```

**What This Does:**
1. Creates `profiles_hot` and `profiles_detail` tables
2. Migrates 9,938 profiles from `profiles` → hot/detail
3. Preserves all 5,002 embeddings (saves $30 in OpenAI costs)
4. Splits narrow (hot) and long (detail) fields

**Expected Output:**
```
2025-10-10 - INFO - Creating hot/detail schema tables...
2025-10-10 - INFO - ✅ Hot/detail tables created
2025-10-10 - INFO - Starting migration from profiles → hot/detail schema...
2025-10-10 - INFO - Found 9,938 profiles to migrate
Migrating: 100%|██████████| 9938/9938 [00:30<00:00, 331 profiles/s]
2025-10-10 - INFO - ✅ Migration complete: 9,938 migrated, 0 skipped
2025-10-10 - INFO - 📊 Embeddings preserved: 5,002/9,938 profiles
2025-10-10 - INFO - 🎉 Migration complete!
```

**Verify Migration:**
```bash
cd "/Users/chromatrical/CAREER/Side Projects/WebApplication" && \
PGPASSWORD=postgres psql -h 127.0.0.1 -p 5432 -U postgres -d profiles << 'SQL'
-- Check hot table
SELECT
    COUNT(*) as total,
    COUNT(embedding) as with_embeddings,
    ROUND(AVG(quality_score)::numeric, 2) as avg_quality
FROM profiles_hot
WHERE is_deleted = FALSE;

-- Check detail table
SELECT COUNT(*) as total FROM profiles_detail;

-- Sample joined data
SELECT
    h.full_name,
    h.job_title,
    h.location_country,
    h.embedding IS NOT NULL as has_embedding,
    d.summary IS NOT NULL as has_summary
FROM profiles_hot h
LEFT JOIN profiles_detail d ON h.id = d.id
LIMIT 5;
SQL
```

---

### **Step 6: Load Incremental Data from S3**

Now load additional data from your S3 Parquet file. This will:
- Skip existing profiles (deduplication by `linkedin_username`)
- Only load new profiles
- Use batch processing

**Option A: Load with Limit (Safe for Testing)**

```bash
# Load 100K new profiles
cd "/Users/chromatrical/CAREER/Side Projects/WebApplication" && \
poetry run python3 << 'EOF'
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

# TODO: Create S3 → staging loader
# This will require a new script: scripts/load_from_s3.py
# For now, you can download a sample and use existing load_parquet_to_staging.py

print("Loading from S3 requires implementing S3 → staging pipeline")
print("Current flow: S3 → Download → load_parquet_to_staging.py → load_to_core.py")
EOF
```

**Option B: Load Full Dataset (Production)**

```bash
# Load all new profiles from S3
cd "/Users/chromatrical/CAREER/Side Projects/WebApplication" && \
poetry run python3 scripts/load_from_s3.py
```

**⚠️ Note:** You'll need to implement `scripts/load_from_s3.py` to:
1. Stream from S3 using DuckDB
2. Filter out existing linkedin_usernames
3. Batch insert to staging
4. Transform to hot/detail

---

### **Step 7: Generate Embeddings for New Profiles**

Once new profiles are loaded, generate embeddings for profiles without them:

```bash
cd "/Users/chromatrical/CAREER/Side Projects/WebApplication" && \
poetry run python3 -m backend.data_pipeline.embeddings.generate
```

**Performance Estimates:**
- Speed: ~37 profiles/second
- Cost: ~$0.006 per 1,000 profiles
- Time for 1M profiles: ~7.5 hours
- Cost for 1M profiles: ~$60

---

### **Step 8: Calculate Hotness Scores**

```bash
cd "/Users/chromatrical/CAREER/Side Projects/WebApplication" && \
poetry run python3 jobs/promote_hot.py calculate
```

**Hotness Formula:**
```
hotness = α (quality: 0-50)
        + β (recency: 0-30)
        + γ (completeness: 0-20)
        + δ (engagement: query_count + click_count*2)
```

---

### **Step 9: Build Indexes**

**⚠️ IMPORTANT:** Build indexes AFTER bulk loading data!

```bash
cd "/Users/chromatrical/CAREER/Side Projects/WebApplication" && \
PGPASSWORD=postgres psql -h 127.0.0.1 -p 5432 -U postgres -d profiles -f sql/03_indexes.sql
```

**Index Build Times (M2 MacBook Air):**
- Primary filters: ~2-5 minutes
- Composite indexes: ~5-10 minutes
- GIN indexes: ~10-15 minutes
- Trigram indexes: ~5-10 minutes
- **HNSW vector index: ~30-60 minutes** (for 5M profiles)

**Total: 60-90 minutes**

---

### **Step 10: Test Search API**

```bash
# Start API server
cd "/Users/chromatrical/CAREER/Side Projects/WebApplication" && \
./start_api.sh
```

**Test Endpoints:**

```bash
# Health check
curl http://localhost:8000/health

# Search
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "senior software engineer python",
    "limit": 10,
    "country": "United States"
  }'

# Get profile
curl http://localhost:8000/profile/YOUR-PROFILE-ID
```

---

## 🔍 Troubleshooting

### **Issue: S3 Access Denied**

```bash
# Check credentials
cd "/Users/chromatrical/CAREER/Side Projects/WebApplication" && \
poetry run python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('AWS Key:', os.getenv('AWS_ACCESS_KEY_ID')[:10] + '...')
print('S3 Path:', os.getenv('PARQUET_S3_PATH'))
"
```

**Solutions:**
1. Verify IAM policy includes `s3:GetObject` permission
2. Check bucket region matches `AWS_REGION` in .env
3. For public buckets, credentials may not be needed
4. Test with AWS CLI: `aws s3 ls s3://your-bucket-name/`

---

### **Issue: Database Connection Failed**

```bash
# Check Docker containers
docker compose ps

# Restart if needed
docker compose restart postgres

# Check logs
docker compose logs postgres | tail -50
```

---

### **Issue: Out of Memory During Index Build**

**Solution:** Increase Docker RAM allocation:
1. Docker Desktop → Settings → Resources
2. Set Memory to 12GB (currently 8GB)
3. Restart Docker

Or build indexes in smaller batches:
```sql
-- Build one index at a time
CREATE INDEX CONCURRENTLY idx_hot_embedding_hnsw
ON profiles_hot USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 200)
WHERE embedding IS NOT NULL;
```

---

## 📊 Data Migration Status

### **Current State**
- **Old schema:** 9,938 profiles in `profiles` table
- **Embeddings:** 5,002 profiles (50%)
- **Quality:** Average 0.85, 82% high-quality (≥0.7)

### **After Migration**
- **New schema:** `profiles_hot` + `profiles_detail`
- **Data preserved:** 100% migrated
- **Embeddings preserved:** 5,002 (saves $30)
- **Ready for incremental loading**

---

## 🚀 Next Steps After Migration

1. **Load 1M test sample** from S3 → profiles_hot
2. **Generate embeddings** for new profiles (~7 hours)
3. **Build HNSW index** (~60 minutes)
4. **Test search performance** (target: 100-300ms)
5. **Scale to full 51M** if performance is acceptable

---

## 📖 Additional Resources

- [Architecture Overview](./README.md)
- [Phase Status](./PHASE_STATUS.md)
- [Negative Spaces Guide](./NEGATIVE_SPACES_GUIDE.md)
- [Index Report](./INDEX_REPORT.md)

---

**Questions?** Check the [troubleshooting section](#-troubleshooting) or review logs:
```bash
# API logs
docker compose logs fastapi

# Database logs
docker compose logs postgres

# Application logs
tail -f logs/*.log
```
