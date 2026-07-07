# PROSPECTIQ - Scaling to 51M Profiles Guide

**Target**: Scale from 497K → 51M+ profiles on Render with GitHub auto-deploy
**Your Dataset**: 96M rows (15GB parquet) in `data/USA_filtered.parquet`

---

## 📊 Current State vs Target State

| Metric | Current (497K) | Target (51M) | Scaling Factor |
|--------|----------------|--------------|----------------|
| **Profiles** | 497,552 | 51,000,000 | 102x |
| **Database Size** | ~2 GB | ~200-300 GB | 100-150x |
| **With Embeddings** | ~4 GB | ~400-500 GB | 100-125x |
| **Index Size** | ~500 MB | ~50-75 GB | 100-150x |
| **Query Time** | 500-1000ms | 800-2000ms | 1.6-2x |
| **RAM Required** | 4-8 GB | 32-64 GB | 8x |

---

## 🎯 Phased Scaling Strategy

### Phase 1: Initial Deployment (1M Profiles) ✅ **START HERE**
**Goal**: Deploy working MVP with 1M best profiles
**Timeline**: 1-2 days
**Cost**: $25-35/month

#### Why Start with 1M?
- ✅ Validate deployment pipeline
- ✅ Test performance at moderate scale
- ✅ Manageable costs while testing
- ✅ Fast iteration and debugging
- ✅ Prove business model before full investment

#### Steps

**1. Extract 1M Best Profiles**
```bash
# Run locally to create 1M subset
poetry run python scripts/prepare_1m_dataset.py

# This creates: data/USA_1M_test.parquet (~500MB)
# Based on quality score ranking
```

**2. Deploy to Render (GitHub Auto-Deploy)**

Create `.github/workflows/deploy-render.yml`:
```yaml
name: Deploy to Render

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Trigger Render Deploy
        run: |
          curl -X POST "${{ secrets.RENDER_DEPLOY_HOOK_URL }}"
```

**3. Set Up Render**

Go to [render.com](https://render.com):

a) **Connect GitHub Repository**
   - Click "New" → "Blueprint"
   - Select your repository
   - Render will detect `render.yaml`

b) **Configure Environment Variables**
   ```bash
   OPENAI_API_KEY=sk-your-key
   JWT_SECRET_KEY=<openssl rand -hex 32>
   ADMIN_PASSWORD=<secure-password>
   ENVIRONMENT=production
   CORS_ORIGINS=https://your-app.onrender.com
   ```

c) **Choose Database Plan**
   - **Standard**: $7/month - 1 GB RAM, 10 GB storage ❌ Too small
   - **Standard Plus**: $90/month - 4 GB RAM, 512 GB storage ✅ **Recommended**
   - **Pro**: $200/month - 8 GB RAM, 1 TB storage ⭐ Best performance

d) **Web Service Plan**
   - **Starter**: $7/month - 512 MB RAM ❌ Too small
   - **Standard**: $25/month - 2 GB RAM ✅ **Start here**
   - **Pro**: $85/month - 4 GB RAM ⭐ Better for 1M+

**4. Load 1M Profiles**

After deployment, use Render Shell:
```bash
# Option 1: Via Render Shell (Dashboard → Shell)
poetry run python -m backend.data_pipeline.ingestion.load_incremental data/USA_1M_test.parquet

# Option 2: Via SSH (if enabled)
ssh render
poetry run python -m backend.data_pipeline.ingestion.load_incremental data/USA_1M_test.parquet
```

**5. Generate Embeddings (Optional for Phase 1)**
```bash
# In Render Shell
poetry run python -m backend.data_pipeline.embeddings.generate

# ~$10-20 in OpenAI credits for 1M profiles
```

**Phase 1 Cost Estimate**:
- Render Standard Plus DB: $90/month
- Render Standard Web: $25/month
- **Total**: $115/month

**Phase 1 Performance**:
- Query time: 600-1200ms
- Concurrent users: 50-100
- Uptime: 99.5%

---

### Phase 2: Scale to 10M Profiles ⭐ **RECOMMENDED PRODUCTION**
**Goal**: Production-ready with 10M high-quality profiles
**Timeline**: 1-2 weeks after Phase 1
**Cost**: $200-300/month

#### Why 10M is the Sweet Spot?
- ✅ Excellent coverage of US market
- ✅ Manageable database size (~120 GB)
- ✅ Sub-2s query performance
- ✅ Reasonable costs
- ✅ Room for growth

#### Infrastructure Requirements

**Database**: Render Pro PostgreSQL
- Plan: $200/month
- RAM: 8 GB
- Storage: 1 TB (you'll use ~150 GB)
- CPU: 4 vCPU
- Connections: 500 max

**Web Service**: Render Pro
- Plan: $85/month
- RAM: 4 GB
- CPU: 2 vCPU
- Instances: 2 (for redundancy)

**Redis** (Optional but recommended)
- Plan: $10/month
- RAM: 256 MB
- Used for: Query caching, rate limiting

#### Data Selection Strategy

**Option A: Top 10M by Quality Score** (Recommended)
```python
# Run locally
import pyarrow.parquet as pq
import pyarrow.compute as pc

# Read parquet
table = pq.read_table("data/USA_filtered.parquet")

# Sort by quality_score descending
sorted_indices = pc.sort_indices(table, sort_keys=[("quality_score", "descending")])
sorted_table = pc.take(table, sorted_indices)

# Take top 10M
top_10m = sorted_table.slice(0, 10_000_000)

# Write to new file
pq.write_table(top_10m, "data/USA_10M_best.parquet", compression='snappy')
```

**Option B: Stratified Sample** (Better diversity)
```python
# Sample across industries and regions
# Ensures coverage of all major sectors
# See: scripts/create_stratified_sample.py (create this)
```

#### Loading Strategy

**Incremental Loading** (Recommended):
```bash
# Split into chunks for safer loading
python scripts/split_parquet_chunks.py data/USA_10M_best.parquet 1000000

# Load in chunks
for chunk in data/chunks/*.parquet; do
    poetry run python -m backend.data_pipeline.ingestion.load_incremental "$chunk"
done
```

**Phase 2 Cost Breakdown**:
- PostgreSQL Pro: $200/month
- Web Service Pro x2: $170/month
- Redis: $10/month
- **Total**: $380/month

**Phase 2 Performance**:
- Query time: 800-1500ms
- Concurrent users: 200-500
- Database size: ~120 GB
- Uptime: 99.9%

---

### Phase 3: Full Scale 51M Profiles 🚀 **ENTERPRISE**
**Goal**: Maximum dataset with all 51M profiles
**Timeline**: After Phase 2 validation
**Cost**: $500-800/month

#### Infrastructure Requirements

**Database**: Render Enterprise PostgreSQL (Custom)
- Contact Render sales for quote
- RAM: 32-64 GB recommended
- Storage: 1-2 TB
- CPU: 8-16 vCPU
- Read replicas: 2-4 recommended

**Alternative: Migrate to AWS/GCP**
For 51M+ profiles, consider:
- **AWS RDS PostgreSQL**: db.r6g.2xlarge (8 vCPU, 64GB RAM) @ $480/month
- **AWS ECS Fargate**: 4 containers @ $120/month
- **ElastiCache Redis**: cache.r6g.large @ $150/month
- **Total AWS**: ~$750/month (with optimizations)

#### Database Optimization for 51M

**1. Partitioning** (Critical at this scale)
```sql
-- Partition by region for faster queries
CREATE TABLE profiles_partitioned (
    LIKE profiles INCLUDING ALL
) PARTITION BY LIST (region);

-- Create partitions for major regions
CREATE TABLE profiles_california PARTITION OF profiles_partitioned
    FOR VALUES IN ('california');
CREATE TABLE profiles_texas PARTITION OF profiles_partitioned
    FOR VALUES IN ('texas');
-- ... create for all 50 states
```

**2. Advanced Indexing**
```sql
-- Composite index for common filters
CREATE INDEX CONCURRENTLY idx_profiles_industry_region
    ON profiles (industry, region)
    WHERE quality_score > 70;

-- Partial index for high-quality profiles only
CREATE INDEX CONCURRENTLY idx_profiles_quality_high
    ON profiles (quality_score, years_experience)
    WHERE quality_score > 80;

-- GIN index for skills array searches
CREATE INDEX CONCURRENTLY idx_profiles_skills_gin
    ON profiles USING GIN (skills);
```

**3. Query Optimization**
```sql
-- Materialized view for popular searches
CREATE MATERIALIZED VIEW mv_software_engineers AS
SELECT * FROM profiles
WHERE industry = 'computer software'
  AND quality_score > 75
WITH DATA;

-- Refresh periodically (daily)
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_software_engineers;
```

#### Loading 51M Profiles

**Batch Loading Strategy**:
```python
# backend/data_pipeline/ingestion/load_51m_batch.py

import pyarrow.parquet as pq
from tqdm import tqdm

def load_51m_in_batches():
    """Load 51M profiles in 1M batches"""

    BATCH_SIZE = 1_000_000
    input_file = "data/USA_filtered.parquet"

    # Read metadata to get total rows
    parquet_file = pq.ParquetFile(input_file)
    total_rows = parquet_file.metadata.num_rows

    print(f"Total rows: {total_rows:,}")
    print(f"Batch size: {BATCH_SIZE:,}")
    print(f"Total batches: {total_rows // BATCH_SIZE + 1}")

    # Process in batches
    for batch_num in tqdm(range(0, total_rows, BATCH_SIZE)):
        # Read batch
        batch = pq.read_table(
            input_file,
            filters=[("rownum", ">=", batch_num), ("rownum", "<", batch_num + BATCH_SIZE)]
        )

        # Load to database
        load_batch_to_db(batch)

        # Sleep to avoid overwhelming DB
        time.sleep(30)
```

**Estimated Load Time**:
- 51M rows @ 5,000 rows/sec = ~2.8 hours
- With deduplication and validation = ~4-6 hours

**Phase 3 Cost Estimates**:

**Option A: Render Enterprise**
- PostgreSQL Enterprise: ~$500-700/month (custom quote)
- Web Service Pro x4: $340/month
- Redis Pro: $50/month
- **Total**: $890-1,090/month

**Option B: AWS (Recommended for 51M)**
- RDS PostgreSQL (db.r6g.2xlarge): $480/month
- ECS Fargate (4 containers): $120/month
- ElastiCache Redis: $150/month
- Load Balancer: $25/month
- CloudFront CDN: $50/month
- **Total**: $825/month

**Phase 3 Performance**:
- Query time: 1000-2000ms
- Concurrent users: 1000+
- Database size: ~400-500 GB
- Uptime: 99.95%

---

## 🔧 Performance Optimizations for Large Scale

### 1. Connection Pooling
```python
# backend/api/database.py
async def get_pool():
    return await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=10,      # Increase for production
        max_size=100,     # Increase for high load
        max_queries=50000,
        max_inactive_connection_lifetime=300,
        timeout=30,
        command_timeout=60
    )
```

### 2. Query Result Caching (Redis)
```python
# backend/api/search.py
import redis
import json
import hashlib

redis_client = redis.from_url(os.getenv("REDIS_URL"))

async def search_with_cache(query: str, filters: dict):
    # Generate cache key
    cache_key = f"search:{hashlib.md5(json.dumps({query, filters}).encode()).hexdigest()}"

    # Check cache
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Execute query
    results = await execute_search(query, filters)

    # Cache for 5 minutes
    redis_client.setex(cache_key, 300, json.dumps(results))

    return results
```

### 3. Pagination Best Practices
```sql
-- Use cursor-based pagination for large offsets
-- Instead of OFFSET 1000000 (slow)
SELECT * FROM profiles
WHERE id > $last_id
ORDER BY id
LIMIT 100;
```

### 4. Limit Search Scope
```python
# Only search high-quality profiles by default
DEFAULT_MIN_QUALITY = 70

async def search(
    query: str,
    min_quality_score: int = DEFAULT_MIN_QUALITY
):
    # This reduces search space by ~40%
    # 51M → 30M profiles to search
    pass
```

---

## 💰 Cost Optimization Strategies

### 1. Tiered Search Access
```python
# Free tier: Top 100K profiles only
# Basic ($29/mo): Top 1M profiles
# Pro ($99/mo): Top 10M profiles
# Enterprise ($299/mo): All 51M profiles

def get_search_limit(user_tier: str) -> int:
    limits = {
        "free": 100_000,
        "basic": 1_000_000,
        "pro": 10_000_000,
        "enterprise": 51_000_000
    }
    return limits.get(user_tier, 100_000)
```

### 2. Progressive Data Loading
```sql
-- Load high-quality profiles first
-- Priority 1: quality_score > 80 (top 20%)
-- Priority 2: quality_score 60-80 (next 40%)
-- Priority 3: quality_score < 60 (remaining 40%)

-- Start with Priority 1, add others based on demand
```

### 3. Use Read Replicas
```yaml
# render.yaml
databases:
  - name: prospectiq-db-primary
    plan: pro

  - name: prospectiq-db-replica
    plan: standard
    replicaOf: prospectiq-db-primary

# Route read-only queries to replica (90% of traffic)
```

---

## 📊 Recommended Scaling Path

### **Start: 1M Profiles** ($115/month)
**When**: Launching MVP, validating market
**Infrastructure**:
- Render Standard Plus DB ($90/mo)
- Render Standard Web ($25/mo)
**Data**: Top 1M by quality score
**Performance**: 600-1200ms queries
**Users**: 50-100 concurrent

### **Growth: 10M Profiles** ($380/month) ⭐ **RECOMMENDED**
**When**: Product-market fit achieved, scaling users
**Infrastructure**:
- Render Pro DB ($200/mo)
- Render Pro Web x2 ($170/mo)
- Redis ($10/mo)
**Data**: Top 10M by quality score
**Performance**: 800-1500ms queries
**Users**: 200-500 concurrent

### **Enterprise: 51M Profiles** ($825/month)
**When**: Large enterprise customers, high revenue
**Infrastructure**:
- AWS RDS PostgreSQL ($480/mo)
- AWS ECS Fargate ($120/mo)
- ElastiCache Redis ($150/mo)
- ALB + CloudFront ($75/mo)
**Data**: All 51M profiles
**Performance**: 1000-2000ms queries
**Users**: 1000+ concurrent

---

## 🚀 Quick Start: Deploy 1M on Render

### Step 1: Prepare 1M Dataset
```bash
# On your local machine
poetry run python scripts/prepare_1m_dataset.py

# Creates: data/USA_1M_test.parquet (~500MB)
```

### Step 2: Push to GitHub
```bash
git add Dockerfile render.yaml .env.production.example
git commit -m "feat: add Render deployment configuration"
git push origin main
```

### Step 3: Deploy on Render
1. Go to [render.com](https://render.com)
2. Click "New" → "Blueprint"
3. Connect your GitHub repository
4. Render detects `render.yaml` automatically
5. Add environment variables (see below)
6. Click "Apply"

### Step 4: Set Environment Variables
```bash
OPENAI_API_KEY=sk-your-key
JWT_SECRET_KEY=<paste from: openssl rand -hex 32>
ADMIN_PASSWORD=SecurePass2025!
ENVIRONMENT=production
CORS_ORIGINS=https://your-app.onrender.com
```

### Step 5: Load Data
```bash
# Option 1: Upload parquet file to Render (if <500MB)
# Use Render Dashboard → Files → Upload

# Option 2: Load from S3/URL
curl -o data/USA_1M_test.parquet https://your-s3-bucket/USA_1M_test.parquet

# Load into database
poetry run python -m backend.data_pipeline.ingestion.load_incremental data/USA_1M_test.parquet
```

### Step 6: Run Migrations
```bash
# In Render Shell
psql $DATABASE_URL < migrations/001_init_schema.sql
psql $DATABASE_URL < migrations/002_indexes.sql
psql $DATABASE_URL < migrations/003_vector_index.sql
psql $DATABASE_URL < migrations/008_users_and_api_keys.sql
```

### Step 7: Test
```bash
# Health check
curl https://your-app.onrender.com/health

# Search test
curl -X POST https://your-app.onrender.com/search \
  -H "Content-Type: application/json" \
  -d '{"query": "software engineer", "limit": 10}'
```

---

## 📈 Monitoring at Scale

### Key Metrics to Track

**Database**:
- Active connections: Should stay below 80% of max
- Query duration: P95 should be <2s
- Cache hit rate: Aim for >80%
- Disk usage: Monitor growth rate

**Application**:
- Response time: P95 <2s
- Error rate: <0.1%
- Requests/minute: Track peaks
- Memory usage: Stay below 80%

### Tools

**Render Built-in**:
- Logs dashboard
- Metrics dashboard
- Alerts

**External (Recommended)**:
- **Sentry**: Error tracking ($26/mo)
- **DataDog**: Full observability ($15/mo/host)
- **UptimeRobot**: Uptime monitoring (Free)

---

## ⚠️ Common Pitfalls & Solutions

### Pitfall 1: Loading Data Takes Forever
**Problem**: Loading 51M rows at 1000 rows/sec = 14 hours

**Solution**:
```python
# Use optimized bulk insert
# backend/data_pipeline/ingestion/load_optimized.py
# Already exists! Uses COPY command
# Speed: 5,000-10,000 rows/sec = 1.5-3 hours
```

### Pitfall 2: Out of Memory During Load
**Problem**: Loading large parquet exhausts RAM

**Solution**:
```python
# Stream processing instead of loading all at once
def load_in_chunks(file_path, chunk_size=100_000):
    parquet_file = pq.ParquetFile(file_path)
    for batch in parquet_file.iter_batches(batch_size=chunk_size):
        process_batch(batch)
```

### Pitfall 3: Slow Queries After Loading
**Problem**: Forgot to rebuild indexes

**Solution**:
```sql
-- After bulk load, rebuild indexes
REINDEX TABLE CONCURRENTLY profiles;
ANALYZE profiles;  -- Update query planner stats
```

### Pitfall 4: High Costs
**Problem**: $800/month is too expensive

**Solution**:
- Start with 1M profiles ($115/mo)
- Add tiered pricing (charge users)
- Use read replicas for scale
- Implement aggressive caching
- Limit free tier to 100K profiles

---

## 🎯 My Recommendation

### For Launch (Next 3 Months)
**Deploy 1M profiles on Render** ($115/month)
- Fast to deploy (today)
- GitHub auto-deploy working
- Validate product-market fit
- Low cost, low risk
- Easy to scale up later

### For Growth (Months 3-12)
**Scale to 10M profiles** ($380/month)
- Proven demand
- Excellent coverage
- Manageable costs
- Great performance
- Sweet spot for most use cases

### For Enterprise (Year 2+)
**Migrate to AWS with 51M** ($825/month)
- Large customer contracts
- Enterprise SLAs
- Global distribution
- Advanced features
- Revenue justifies cost

---

## 📞 Next Steps

1. **Deploy 1M on Render** (This weekend)
   ```bash
   poetry run python scripts/prepare_1m_dataset.py
   git push origin main
   # Follow Render setup above
   ```

2. **Monitor Performance** (Week 1)
   - Track query times
   - Monitor user behavior
   - Collect feedback

3. **Optimize Queries** (Week 2-4)
   - Add caching
   - Tune indexes
   - Optimize common searches

4. **Plan Scale-Up** (Month 2-3)
   - Prepare 10M dataset
   - Test load process
   - Budget for upgrade

---

**Current Status**: Ready to deploy 1M profiles on Render today! 🚀

**Questions?** Check:
- `DEPLOYMENT_GUIDE.md` - Basic deployment
- `SCALING_TO_51M_GUIDE.md` - This document (scaling strategy)
- Render docs: https://render.com/docs
