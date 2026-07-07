# INSIGHT - Scalable Data Ingestion Architecture

## Problem Statement

The current ingestion pipeline has these limitations:
- **Memory intensive**: Loads 500K+ usernames into RAM for deduplication
- **CPU bound**: Single-threaded transform → validate → dedupe loop
- **Not cloud-ready**: Tightly coupled to local PostgreSQL connection
- **Slow for 51M scale**: Would take 15+ hours to process full dataset

## Solution: Three-Tier Ingestion Architecture

### **Tier 1: Local Development (Current - 500K profiles)**
- ✅ Simple Python script with psycopg
- ✅ In-memory deduplication cache
- ✅ 10K batch inserts
- **Use case**: Local testing, <1M profiles
- **Performance**: 1,000-2,000 rows/sec (~8-15 minutes for 1M)

### **Tier 2: Optimized Local (500K - 2M profiles)**
- 🔧 Database-driven deduplication (no RAM cache)
- 🔧 Parallel processing with multiprocessing
- 🔧 Temporary staging table for batch COPY
- **Use case**: Local machine with 16GB+ RAM, 1M-2M profiles
- **Performance**: 5,000-10,000 rows/sec (~2-3 minutes for 1M)

### **Tier 3: Cloud Production (2M - 51M profiles)**
- ☁️ Distributed worker pool (ECS Fargate / Cloud Run)
- ☁️ S3 → Parquet streaming → PostgreSQL
- ☁️ Redis-based coordination and deduplication
- ☁️ Auto-scaling based on queue depth
- **Use case**: Production deployment, 10M-51M profiles
- **Performance**: 50,000-100,000 rows/sec (~10-15 minutes for 51M)

---

## Tier 2: Optimized Local Ingestion (Implementing Now)

### **Key Optimizations**

#### 1. **Database-Driven Deduplication** (Eliminates RAM bottleneck)
Instead of loading 500K usernames into Python:
```sql
-- Use PostgreSQL for deduplication (much faster)
INSERT INTO profiles (...)
SELECT ... FROM staging
WHERE NOT EXISTS (
    SELECT 1 FROM profiles
    WHERE profiles.linkedin_username = staging.linkedin_username
)
ON CONFLICT (linkedin_username) DO NOTHING;
```

#### 2. **Parallel Processing** (Multi-core CPU utilization)
```python
# Process batches in parallel with 4-8 workers
from concurrent.futures import ProcessPoolExecutor

with ProcessPoolExecutor(max_workers=4) as executor:
    futures = [
        executor.submit(process_batch, batch_data)
        for batch_data in parquet_batches
    ]
```

#### 3. **COPY Protocol** (10x faster than INSERT)
```python
# Use PostgreSQL COPY for bulk inserts (fastest method)
with conn.cursor() as cur:
    with cur.copy("COPY staging FROM STDIN") as copy:
        for row in batch:
            copy.write_row(row)
```

#### 4. **Streaming Parquet Reader** (Low memory footprint)
```python
# Process Parquet in chunks without loading entire file
for batch in pf.ParquetFile(file).iter_batches(batch_size=50000):
    process_batch(batch)  # Only 50K rows in RAM at once
```

---

## Tier 3: Cloud Production Architecture

### **Architecture Diagram**

```
┌─────────────────────────────────────────────────────────────┐
│                         S3 Bucket                           │
│   linkedin_profiles_1m.parquet (300 MB)                     │
│   linkedin_profiles_10m.parquet (3 GB)                      │
│   linkedin_profiles_51m.parquet (15 GB)                     │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ↓
┌────────────────────────────────────────────────────────────┐
│              Ingestion Coordinator (FastAPI)               │
│   - Splits Parquet into chunks (1M rows each)              │
│   - Pushes chunk jobs to SQS queue                         │
│   - Monitors progress via Redis                            │
└────────────────┬───────────────────────────────────────────┘
                 │
                 ↓
┌────────────────────────────────────────────────────────────┐
│                   SQS Queue (FIFO)                         │
│   Job 1: rows 0-1M                                         │
│   Job 2: rows 1M-2M                                        │
│   Job 3: rows 2M-3M                                        │
│   ...                                                      │
└────────────────┬───────────────────────────────────────────┘
                 │
                 ↓
┌────────────────────────────────────────────────────────────┐
│         Ingestion Workers (ECS Fargate)                    │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│   │ Worker 1 │  │ Worker 2 │  │ Worker 3 │  ... (10-50)  │
│   └────┬─────┘  └────┬─────┘  └────┬─────┘               │
│        │             │             │                       │
│        └─────────────┴─────────────┴───────────────────┐  │
└──────────────────────────────────────────────────────┬─┘  │
                                                        │    │
                                                        ↓    │
┌────────────────────────────────────────────────────────────┐
│              Redis (Deduplication Cache)                   │
│   - Bloom filter for username existence check             │
│   - Distributed lock for batch coordination                │
│   - Progress tracking (rows processed/loaded/failed)       │
└────────────────┬───────────────────────────────────────────┘
                 │
                 ↓
┌────────────────────────────────────────────────────────────┐
│         PostgreSQL RDS (Multi-AZ + Read Replica)           │
│   - Primary: Write ingestion data                          │
│   - Replica: Serve API queries (no performance impact)     │
└────────────────────────────────────────────────────────────┘
```

### **Worker Logic (Each ECS Task)**

```python
# backend/data_pipeline/ingestion/cloud_worker.py

import boto3
import redis
import asyncpg
from pyarrow import fs, parquet as pq

async def process_chunk_job(job: dict):
    """
    Process a chunk of Parquet data from S3

    Job format:
    {
        "s3_path": "s3://bucket/linkedin_profiles_51m.parquet",
        "start_row": 0,
        "end_row": 1000000,
        "chunk_id": "chunk_0001"
    }
    """
    # 1. Stream Parquet chunk from S3 (no full download)
    s3_fs = fs.S3FileSystem()
    parquet_file = pq.ParquetFile(s3_fs.open_input_file(job['s3_path']))

    # 2. Read only the requested chunk (memory efficient)
    batch_iter = parquet_file.iter_batches(
        batch_size=10000,
        columns=['linkedin_username', 'full_name', ...],  # Select columns
        use_threads=True
    )

    # 3. Connect to Redis for deduplication
    redis_client = redis.Redis(host=REDIS_HOST, decode_responses=True)

    # 4. Connect to PostgreSQL
    pool = await asyncpg.create_pool(PG_DSN, min_size=1, max_size=2)

    # 5. Process batches
    stats = {'loaded': 0, 'duplicates': 0, 'failed': 0}

    async with pool.acquire() as conn:
        async with conn.transaction():
            for batch in batch_iter:
                # Transform data
                rows = [transform_row(row) for row in batch.to_pylist()]

                # Check Redis bloom filter (fast duplicate check)
                unique_rows = []
                for row in rows:
                    username = row['linkedin_username']

                    # Check Redis bloom filter first (O(1))
                    if redis_client.bf().exists('linkedin_usernames', username):
                        stats['duplicates'] += 1
                        continue

                    unique_rows.append(row)

                    # Add to bloom filter
                    redis_client.bf().add('linkedin_usernames', username)

                # Bulk insert with COPY protocol
                if unique_rows:
                    try:
                        await conn.copy_records_to_table(
                            'profiles',
                            records=unique_rows,
                            columns=[...]
                        )
                        stats['loaded'] += len(unique_rows)
                    except Exception as e:
                        stats['failed'] += len(unique_rows)
                        logger.error(f"Insert failed: {e}")

    # 6. Update progress in Redis
    redis_client.hincrby(f"ingestion:progress", "loaded", stats['loaded'])
    redis_client.hincrby(f"ingestion:progress", "duplicates", stats['duplicates'])

    return stats
```

### **Coordinator API Endpoints**

```python
# POST /api/v1/ingestion/start
# - Splits Parquet into chunks
# - Creates SQS jobs
# - Returns job_id for tracking

# GET /api/v1/ingestion/status/{job_id}
# - Queries Redis for progress
# - Returns: {loaded, duplicates, failed, progress_pct, eta}

# POST /api/v1/ingestion/cancel/{job_id}
# - Stops workers gracefully
# - Rolls back incomplete batches
```

---

## Performance Comparison

| Tier | Profiles | Time | Cost | CPU Cores | Memory |
|------|----------|------|------|-----------|--------|
| **Tier 1** (Current) | 500K | 8 min | $0 | 1 | 2 GB |
| **Tier 1** | 1M | 15 min | $0 | 1 | 4 GB |
| **Tier 2** (Optimized) | 1M | 2 min | $0 | 4-8 | 4 GB |
| **Tier 2** | 2M | 4 min | $0 | 8 | 8 GB |
| **Tier 3** (Cloud) | 10M | 10 min | $5 | 40 (10 workers) | 20 GB |
| **Tier 3** | 51M | 15 min | $20 | 200 (50 workers) | 100 GB |

### **Cost Breakdown (Tier 3 - AWS)**

**One-time 51M profile ingestion:**
- ECS Fargate: 50 workers × 0.25 hours × $0.04/hr = **$0.50**
- RDS I/O: 51M writes × $0.20/1M = **$10.20**
- S3 Data Transfer: 15 GB × $0.09/GB = **$1.35**
- Redis: 4 GB × $0.023/hr = **$0.10**
- **Total: ~$12** (one-time cost)

**Ongoing incremental loads (1M/month):**
- ~$0.25/month for incremental updates

---

## Migration Path

### **Phase 1: Now (Local - Tier 1)**
✅ Use current `load_incremental.py` for 500K → 1M
- Works fine for current scale
- No changes needed
- 15 minutes is acceptable

### **Phase 2: This Week (Local - Tier 2)**
🔧 Implement optimized local loader:
1. Database-driven deduplication
2. COPY protocol for inserts
3. Optional parallel processing
- Use for 1M → 2M locally
- 2-4 minutes load time

### **Phase 3: Before Cloud Deploy (Tier 3)**
☁️ Implement cloud ingestion service:
1. S3 + SQS + ECS workers
2. Redis bloom filter coordination
3. FastAPI coordinator with progress tracking
- Use for 2M → 51M in production
- 10-15 minutes for full dataset

---

## Decision Matrix

**Use Tier 1 (Current) if:**
- Local development/testing
- <1M profiles
- No rush (15 min is fine)

**Use Tier 2 (Optimized) if:**
- 1M-2M profiles locally
- Want faster load times (2-4 min)
- Have 8+ CPU cores

**Use Tier 3 (Cloud) if:**
- Production deployment
- 10M-51M profiles
- Need horizontal scaling
- Regular data updates

---

## Next Steps

1. **Immediate**: Use Tier 1 to load 1M profiles (15 min)
2. **This week**: Implement Tier 2 optimizations (optional)
3. **Before deploy**: Implement Tier 3 cloud service (required for 51M)

**Recommendation**:
- Use Tier 1 NOW to get to 1M quickly
- Deploy to cloud at 1M with Tier 3 architecture
- Skip Tier 2 unless you need 2M+ locally
