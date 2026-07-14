# INSIGHT - Hybrid System Setup

**Best of Both Worlds:** Fast PostgreSQL search + Full S3 analytics

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Frontend (Search & Browse)                     │
└──────────┬──────────────────────┬────────────────┘
           │                      │
           ↓                      ↓
┌──────────────────────┐  ┌─────────────────────┐
│  PostgreSQL API      │  │  DuckDB API         │
│  (Fast Search)       │  │  (Analytics)        │
│  - Top 500K profiles │  │  - All 51M profiles │
│  - <100ms queries    │  │  - 10-15 min queries│
│  - Embeddings ready  │  │  - Zero disk usage  │
└──────────┬───────────┘  └──────────┬──────────┘
           │                         │
           ↓                         ↓
    ┌────────────┐           ┌──────────────┐
    │ PostgreSQL │           │   S3 Bucket  │
    │  ~20 GB    │           │   15.15 GB   │
    └────────────┘           └──────────────┘
```

## Use Cases

### PostgreSQL (Fast Search)
- ✅ Real-time user searches
- ✅ Find by name, title, skills
- ✅ Filter by country, industry
- ✅ Semantic "find similar" (if embeddings enabled)
- ⚡ Speed: <100ms

### DuckDB (Analytics)
- ✅ "Show me all 51M profiles"
- ✅ Industry statistics
- ✅ Country distributions
- ✅ Data exports
- ⏱️  Speed: 10-15 minutes (occasional use)

---

## Setup Steps

### Step 1: Extract Top 500K Profiles (15 minutes)

```bash
cd "/Users/chromatrical/CAREER/Side Projects/51M-Linkedin-user-DB" && \
poetry run python3 scripts/extract_top_500k.py
```

**This will:**
- Query S3 for highest quality profiles
- Select 500K with most complete data
- Stratify by country + industry for diversity
- Save to: `data/top_500k_profiles.parquet` (~500 MB)

**What makes a "top" profile:**
- Has name, job title, location
- Has skills (weighted 2x)
- Has experience, company, industry
- Quality score ≥ 5 out of 9 fields

---

### Step 2: Load to PostgreSQL (5 minutes)

```bash
cd "/Users/chromatrical/CAREER/Side Projects/51M-Linkedin-user-DB" && \
poetry run load-parquet data/top_500k_profiles.parquet
```

**This loads to staging table with validation**

Then transform to core schema:

```bash
poetry run load-core
```

**Verify:**
```bash
PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres -d profiles -c \
  "SELECT COUNT(*) FROM profiles WHERE is_deleted = FALSE;"
```

Should show: `~500,000`

---

### Step 3: Build Indexes (30-45 minutes)

```bash
PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres \
  -d profiles -f sql/03_indexes.sql
```

**Creates:**
- Full-text search indexes (GIN)
- B-tree indexes on filters (country, industry, experience)
- Composite indexes for common queries

**Note:** This takes time but massively speeds up queries

---

### Step 4: (Optional) Generate Embeddings (60-90 minutes, ~$10)

**Skip this if you only want keyword search**

```bash
poetry run generate-embeddings
```

**This will:**
- Generate OpenAI embeddings for semantic search
- Cost: ~500K profiles × $0.02/1K = **~$10**
- Enables "find similar" features
- Enables semantic search ("AI expert" finds "ML researcher")

**Monitor progress:**
- Watch terminal for progress bar
- Check `embedding_checkpoint` table for resume capability

---

### Step 5: Start PostgreSQL API (instant)

```bash
./start_api.sh
```

**API will run at:** http://localhost:8000

**Test it:**
```bash
curl http://localhost:8000/health
```

Should return:
```json
{
  "status": "healthy",
  "profiles_total": 500000,
  "profiles_with_embeddings": 500000  // if you ran Step 4
}
```

---

### Step 6: Update Frontend (optional)

The frontend currently uses DuckDB API. To use PostgreSQL:

**Edit `frontend/search.js` and `frontend/results.js`:**

Change:
```javascript
const API_BASE_URL = 'http://localhost:8000';  // DuckDB API
```

To:
```javascript
const API_BASE_URL = 'http://localhost:8000';  // PostgreSQL API (same port!)
```

**Note:** Both APIs run on port 8000, just start the one you want to use.

---

## Using the Hybrid System

### For Fast Search (PostgreSQL)

1. Start PostgreSQL API:
```bash
./start_api.sh
```

2. Open frontend:
```bash
open frontend/index.html
```

3. Search 500K profiles with <100ms response

---

### For Full Analytics (DuckDB)

1. Start DuckDB API:
```bash
./start_duckdb_api.sh
```

2. Run analytics queries:
```bash
curl 'http://localhost:8000/stats'
```

3. Browse all 51M profiles (slow but comprehensive)

---

## Performance Comparison

| Metric | PostgreSQL | DuckDB + S3 |
|--------|-----------|-------------|
| **Profiles** | 500K | 51M |
| **Disk Usage** | ~20 GB | 0 GB |
| **Query Speed** | <100ms | 10-15 min |
| **Use Case** | Real-time search | Analytics |
| **Cost** | $0-10 (embeddings) | $0 |

---

## Disk Space Check

**Before starting:**
```bash
df -h / | tail -1
```

**You need:**
- 500 MB for extracted Parquet
- ~20 GB for PostgreSQL data
- **Total: ~21 GB**

**You have:** 42 GB free ✅

---

## Troubleshooting

### Extraction Times Out

**Problem:** S3 download takes >30 minutes

**Solution:**
- Check internet speed
- Retry during off-peak hours
- Script has progress indicators

---

### PostgreSQL Out of Memory

**Problem:** Index building fails

**Solution:**
```bash
# Increase Docker memory to 8GB
# Docker Desktop → Settings → Resources → Memory → 8GB
```

---

### Embeddings Too Expensive

**Skip Step 4!** You can still use:
- ✅ Keyword search
- ✅ Filters (country, industry, skills)
- ✅ Full-text search
- ❌ Semantic search (requires embeddings)

---

## Next Steps After Setup

### Add Features

1. **Profile Detail View**
   - Click row to show full profile
   - Display all fields
   - Add "Find Similar" button (if embeddings enabled)

2. **Export Results**
   - Export search results to CSV
   - Email profiles
   - Share search URLs

3. **Advanced Filters**
   - Company size
   - Education level
   - Years in role
   - Certifications

4. **Saved Searches**
   - Save filter combinations
   - Email alerts for new matches
   - Dashboard with saved searches

---

## Monitoring

### Check PostgreSQL Status
```bash
PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres -d profiles -c "
SELECT
    COUNT(*) as total,
    COUNT(embedding) as with_embeddings,
    ROUND(AVG(content_quality_score)::numeric, 2) as avg_quality
FROM profiles
WHERE is_deleted = FALSE;
"
```

### Check Disk Usage
```bash
docker system df
```

### Check API Logs
```bash
# PostgreSQL API logs
tail -f logs/api.log  # if logging to file

# Or watch terminal where you ran ./start_api.sh
```

---

## Scaling Beyond 500K

If you need more profiles:

**Option 1: Extract 1M profiles**
- Edit `extract_top_500k.py`
- Change `LIMIT 500000` to `LIMIT 1000000`
- Re-run extraction
- **Disk needed:** ~40 GB
- **Embedding cost:** ~$20

**Option 2: Load specific countries/industries**
- Add WHERE clause to extraction query
- Example: Only USA profiles
- Reduces size while staying focused

**Option 3: Full 51M (not recommended)**
- **Disk needed:** ~500 GB (you only have 42 GB)
- **Embedding cost:** ~$1,000
- Requires external storage or cloud deployment

---

## Security Reminder

⚠️ **Don't forget to rotate your AWS credentials!**

See: `../guides/SECURITY.md`

---

## Summary

**You're setting up:**
- ✅ PostgreSQL with 500K best profiles for fast search
- ✅ DuckDB for occasional analytics on all 51M
- ✅ Clean frontend for both use cases
- ✅ Optional embeddings for semantic search

**Total time:** 1-2 hours
**Total cost:** $0-10 (if you want embeddings)
**Total disk:** ~21 GB

**Ready to start?** Run Step 1! 🚀
