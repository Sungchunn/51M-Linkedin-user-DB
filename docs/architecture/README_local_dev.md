# INSIGHT - Local Development Guide (MacBook Air M2)

Complete setup guide for hybrid architecture with Postgres hot serving, Redis caching, and DuckDB analytics.

## Architecture Overview

```
Client → FastAPI backend
         ├─▶ Postgres (+pgvector, HNSW) [hot serving, 3-5M profiles]
         ├─▶ Redis [result + profile cache]
         └─▶ DuckDB + httpfs → S3 Parquet [full 51M analytics]
```

### Key Optimizations for M2

- **VECTOR(384)** instead of 1536-d = 60% disk savings
- **Hot/Detail split** = narrow serving table, detail on-demand
- **HNSW indexes** = m=16, ef_construction=200 (M2-tuned)
- **Named volumes** = avoid iCloud/Dropbox sync
- **2GB shared_buffers** = 25% of Docker RAM (8GB)
- **Resumable embeddings** = 50K batches with checkpointing

---

## Prerequisites

### 1. System Requirements

- MacBook Air M2 (or M1/M3)
- macOS Sonoma or later
- Docker Desktop for Mac (allocate 8GB+ RAM)
- Python 3.11+
- ~50GB free disk space

### 2. Install Dependencies

```bash
# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install Python dependencies
poetry install

# Activate virtual environment
poetry shell
```

### 3. Environment Variables

Create `.env` file in project root:

```bash
# Database
PG_DSN=postgresql://postgres:postgres@localhost:5432/profiles

# OpenAI (for embeddings)
OPENAI_API_KEY=sk-...

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_ENABLED=true

# DuckDB S3 (optional - for full 51M dataset analytics)
PARQUET_S3_PATH=s3://your-bucket/linkedin_profiles_51m.parquet
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# API
API_PORT=8000

# Embedding settings
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=384
BATCH_SIZE_IO=50000
BATCH_SIZE_EMBED=100
MIN_QUALITY_SCORE=0.7

# Database pool settings
DB_POOL_MIN_SIZE=5
DB_POOL_MAX_SIZE=20
```

---

## Quick Start

### 1. Start Services

```bash
make up
```

This starts:
- **Postgres** on port 5432 (with pgvector)
- **Redis** on port 6379 (2GB cache)
- **Pgweb** on port 8081 (optional DB UI)

Verify services:
```bash
docker-compose ps
```

### 2. Initialize Database

```bash
make db/init
```

This runs:
- `01_extensions.sql` - Install pgvector, pg_trgm
- `02_schema.sql` - Create profiles_hot, profiles_detail, checkpoints
- `03_indexes.sql` - Create HNSW + supporting indexes

### 3. Migrate Existing Data

If you have 10M profiles in the old `profiles` table:

```bash
make db/migrate
```

This runs `04_migration_from_existing.sql`:
- Calculates hotness scores (quality + recency + completeness)
- Backfills profiles_hot and profiles_detail
- Optional: Limit to top 5M (uncomment in SQL)

**Estimated time:** 10-30 minutes for 10M profiles

### 4. Generate Embeddings

#### Option A: OpenAI API (Fast, ~$200 for 5M profiles)

```bash
make embed/openai
```

#### Option B: Local MPS (Free, slower)

First install sentence-transformers:
```bash
pip install sentence-transformers torch
```

Then run:
```bash
make embed/mps
```

**Estimated time:**
- OpenAI: 2-3 hours for 5M profiles (~37 profiles/sec)
- MPS: 6-12 hours for 5M profiles (~15 profiles/sec)

**Resumable:** If interrupted, re-run the same command to resume from checkpoint.

Check progress:
```bash
make embed/status
```

### 5. Start API Server

```bash
make api/start
```

API available at: http://localhost:8000

Test endpoints:
```bash
make api/test
```

---

## Database Schema

### profiles_hot (Narrow Serving Table)

```sql
CREATE TABLE profiles_hot (
    id UUID PRIMARY KEY,
    linkedin_username VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    job_title VARCHAR(255),
    company_name VARCHAR(255),
    headline VARCHAR(500),                -- Truncated

    -- Filters
    location_country VARCHAR(100),
    industry VARCHAR(100),
    seniority_level VARCHAR(50),
    years_experience INT,
    top_skills TEXT[],                    -- Top 10 only

    -- 384-d vector (60% smaller than 1536-d)
    embedding VECTOR(384),
    embedding_generated_at TIMESTAMPTZ,

    -- Hotness ranking
    quality_score DECIMAL(3,2),
    hotness_score DECIMAL(10,2) DEFAULT 0,
    query_count_7d INT DEFAULT 0,
    click_count_7d INT DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_promoted_at TIMESTAMPTZ,
    is_deleted BOOLEAN DEFAULT FALSE
);
```

### profiles_detail (Long Fields)

```sql
CREATE TABLE profiles_detail (
    id UUID PRIMARY KEY REFERENCES profiles_hot(id),
    summary TEXT,                         -- Full text
    experience_json JSONB,
    education_json JSONB,
    email VARCHAR(255),
    all_skills TEXT[],                    -- All skills
    ...
);
```

---

## API Endpoints

### POST /search

Hybrid semantic + keyword search:

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "senior software engineer with Python",
    "limit": 20,
    "country": "United States",
    "industry": "Information Technology",
    "min_experience": 5,
    "skills": ["Python", "AWS"]
  }'
```

**Response:**
```json
{
  "results": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "linkedin_username": "john-doe",
      "full_name": "John Doe",
      "job_title": "Senior Software Engineer",
      "company_name": "FAANG Corp",
      "relevance_score": 0.92,
      "hotness_score": 87.5
    }
  ],
  "total_results": 15,
  "search_time_ms": 124,
  "query": "senior software engineer with Python"
}
```

### GET /profile/{id}

Get full profile details:

```bash
curl http://localhost:8000/profile/123e4567-e89b-12d3-a456-426614174000
```

### GET /stats/industry

Industry statistics from DuckDB (full 51M dataset):

```bash
curl http://localhost:8000/stats/industry?limit=20
```

### GET /stats/country

Country statistics:

```bash
curl http://localhost:8000/stats/country?limit=20
```

---

## Jobs

### Calculate Hotness Scores

```bash
make promote/calculate
```

Updates `hotness_score` for all profiles using:
- Quality score (α = 50)
- Recency (β = 5-30)
- Completeness (γ = 20)
- Engagement (δ = query/click counts)

### Promote Top Profiles

```bash
make promote/run
```

Promotes top 5M profiles to hot serving table (soft-deletes rest).

### Reset Weekly Counters

Run weekly to reset `query_count_7d` and `click_count_7d`:

```bash
python jobs/promote_hot.py reset-counters
```

---

## DuckDB Analytics

Query full 51M dataset on S3 without local copy:

```python
from backend.duck import run_duckdb_query

# Get industry distribution
results = await run_duckdb_query("""
    SELECT Industry, COUNT(*) as count
    FROM read_parquet('s3://bucket/linkedin_profiles_51m.parquet')
    GROUP BY Industry
    ORDER BY count DESC
    LIMIT 20
""")
```

### Create Dev Sample

Create 1% stratified sample (~510K profiles):

```python
from backend.duck import create_stratified_sample

await create_stratified_sample(
    output_path="data/sample_1pct.parquet",
    sample_pct=0.01,
    strata_cols=["Location Country", "Industry"]
)
```

---

## Performance Tuning

### HNSW Parameters

Query-time tuning:
```sql
SET hnsw.ef_search = 100;  -- Higher = better recall (default 40)
```

Index-time tuning (already set):
```sql
-- m=16, ef_construction=200 (balanced for M2)
CREATE INDEX idx_hot_embedding_hnsw
    ON profiles_hot
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);
```

### Database Settings (Applied via Docker)

```
shared_buffers = 2GB              # 25% of Docker RAM
effective_cache_size = 8GB        # 50% of Docker RAM
maintenance_work_mem = 2GB        # For index builds
work_mem = 64MB
max_wal_size = 4GB
random_page_cost = 1.1            # SSD
effective_io_concurrency = 200
```

### Redis Caching

- **Search results:** 5 min TTL
- **Profile details:** 10 min TTL
- **Max memory:** 2GB (LRU eviction)

---

## Troubleshooting

### Issue: Docker Out of Memory

**Solution:** Allocate more RAM to Docker Desktop
1. Open Docker Desktop → Settings → Resources
2. Set Memory to 8GB+
3. Restart Docker

### Issue: HNSW Index Build Fails

**Solution:** Increase maintenance_work_mem
```bash
docker-compose exec postgres psql -U postgres -d profiles -c \
  "SET maintenance_work_mem = '4GB'; REINDEX INDEX CONCURRENTLY idx_hot_embedding_hnsw;"
```

### Issue: Embedding Generation Slow

**Solutions:**
1. Use OpenAI API instead of local MPS
2. Reduce batch size: `--limit 10000` for testing
3. Check MPS availability: `python -c "import torch; print(torch.backends.mps.is_available())"`

### Issue: Search Returns No Results

**Checklist:**
1. Check if embeddings generated: `make embed/status`
2. Verify HNSW index built: `make stats/size`
3. Check is_deleted flag: `SELECT COUNT(*) FROM profiles_hot WHERE is_deleted = FALSE;`
4. Test keyword search: Query without embedding

### Issue: Port Already in Use

**Solution:** Change port in `.env` and `docker-compose.yml`
```bash
# .env
API_PORT=8001

# docker-compose.yml
ports:
  - "5433:5432"  # Postgres
  - "6380:6379"  # Redis
```

---

## Database Maintenance

### Weekly Tasks

```bash
# Reset engagement counters
python jobs/promote_hot.py reset-counters

# Vacuum
make db/vacuum
```

### Monthly Tasks

```bash
# Full vacuum
docker-compose exec postgres psql -U postgres -d profiles -c "VACUUM FULL ANALYZE profiles_hot;"

# Reindex
docker-compose exec postgres psql -U postgres -d profiles -c "REINDEX INDEX CONCURRENTLY idx_hot_embedding_hnsw;"

# Archive audit logs
docker-compose exec postgres psql -U postgres -d profiles -c "DELETE FROM hot_audit WHERE performed_at < NOW() - INTERVAL '90 days';"
```

---

## Scaling to 51M Profiles

### Strategy

1. **Keep hot serving at 3-5M profiles** (optimize for query speed)
2. **Store full 51M in S3 Parquet** (use DuckDB for analytics)
3. **Promote to hot based on hotness score** (daily job)

### S3 Upload

```bash
# Compress and upload to S3
aws s3 cp data/linkedin_profiles_51m.parquet \
  s3://your-bucket/linkedin_profiles_51m.parquet \
  --storage-class INTELLIGENT_TIERING
```

### Cost Estimate

- **S3 storage:** ~$1-2/month (17GB with intelligent tiering)
- **Embeddings (OpenAI):** ~$200 one-time for 5M profiles
- **DuckDB queries:** Free (httpfs reads from S3)

---

## Development Workflow

### Typical Day-to-Day

```bash
# Start services
make up

# Start API with hot reload
make api/start

# In another terminal: Monitor logs
make logs

# Test API changes
make api/test

# Stop services when done
make down
```

### Testing with Sample Data

```bash
# Load 10K sample
python -m backend.data_pipeline.ingestion.load_incremental \
  data/sample_10k.parquet --limit 10000

# Generate embeddings
make embed/mps

# Promote to hot
make promote/run
```

---

## Useful Commands

```bash
# Check database status
make db/status

# Check table sizes
make stats/size

# View embedding progress
make embed/status

# Tail Postgres logs
docker-compose logs -f postgres

# Connect to database
docker-compose exec postgres psql -U postgres -d profiles

# View recent audit logs
docker-compose exec postgres psql -U postgres -d profiles -c \
  "SELECT * FROM hot_audit ORDER BY performed_at DESC LIMIT 10;"
```

---

## Additional Resources

- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [HNSW Tuning Guide](https://github.com/pgvector/pgvector#hnsw)
- [DuckDB httpfs Extension](https://duckdb.org/docs/extensions/httpfs.html)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

## Support

For issues or questions:
1. Check logs: `make logs`
2. Verify services: `docker-compose ps`
3. Test connectivity: `make api/test`
4. Review database status: `make db/status`

---

**Last updated:** 2025-10-08
