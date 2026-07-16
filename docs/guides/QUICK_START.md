# INSIGHT - Quick Start Guide

## 🚀 Get Started in 3 Steps

### Step 1: Start the API Server

```bash
cd "/Users/chromatrical/CAREER/Side Projects/51M-Linkedin-user-DB" && \
./start_duckdb_api.sh
```

**You should see:**
```
============================================================
🚀 Starting INSIGHT DuckDB API
============================================================

API Features:
  ✅ Browse 51M+ profiles from S3
  ✅ Zero local disk usage
  ✅ Keyword search + filters
  ✅ Country, industry, experience filters

API will be available at: http://localhost:8000
API docs: http://localhost:8000/docs
```

Leave this terminal running.

---

### Step 2: Open the Frontend

In a NEW terminal:
```bash
cd "/Users/chromatrical/CAREER/Side Projects/51M-Linkedin-user-DB/frontend" && \
bun install && \
bun run dev
```

Then open: http://localhost:5500

---

### Step 3: Search!

1. **Try a keyword search:**
   - Type "Python developer" in the keyword field
   - Click "Search"

2. **Try filters:**
   - Select Country: "United States"
   - Select Industry: "Information Technology and Services"
   - Click "Search"

3. **Browse results:**
   - Scroll through the table
   - Click "Next" for more results
   - Click "← Back to Search" to try a new query

---

## ✅ What You Just Built

### Architecture
```
┌─────────────────────────────────────────────┐
│  Frontend (HTML/CSS/JS)                     │
│  - Search form with filters                 │
│  - Scrollable results table                 │
│  - Pagination                                │
└──────────────┬──────────────────────────────┘
               │ HTTP Requests
               ↓
┌─────────────────────────────────────────────┐
│  FastAPI Server (localhost:8000)            │
│  - /search endpoint                          │
│  - /stats endpoint                           │
│  - /countries, /industries filters           │
└──────────────┬──────────────────────────────┘
               │ SQL Queries
               ↓
┌─────────────────────────────────────────────┐
│  DuckDB (In-Memory)                          │
│  - Queries S3 Parquet directly               │
│  - Zero local disk usage                     │
└──────────────┬──────────────────────────────┘
               │ S3 Access
               ↓
┌─────────────────────────────────────────────┐
│  S3 Bucket (Sydney)                          │
│  - 51,352,619 profiles                       │
│  - USA_filtered.parquet (15.15 GB)           │
│  - Read via Access Point                     │
└─────────────────────────────────────────────┘
```

### Key Features

✅ **Zero Disk Usage** - Queries 51M profiles from S3 without local storage
✅ **Fast Search** - 500-2000ms queries across all fields
✅ **Advanced Filters** - Country, industry, experience, skills
✅ **Clean UX** - Modern, responsive design
✅ **Browser Navigation** - Full back button support
✅ **Pagination** - Browse results in pages of 50

---

## 📊 Example Searches

### Find Python Developers in USA
```
Keyword: Python developer
Country: United States
Min Experience: 3
```

### Find Senior AI Researchers
```
Keyword: AI researcher
Min Experience: 10
```

### Browse Tech Industry in California
```
Industry: Information Technology and Services
Keyword: California
```

### Find React Developers
```
Skills: React
Country: United States
Min Experience: 2
```

---

## 🔧 Troubleshooting

### API Won't Start

**Error:** `ModuleNotFoundError: No module named 'duckdb'`

**Fix:**
```bash
poetry install
```

---

### CORS Errors in Browser

**Error:** `Access to fetch... has been blocked by CORS policy`

**Fix:** Make sure API is running at `http://localhost:8000`

Check:
```bash
curl http://localhost:8000/health
```

Should return:
```json
{
  "status": "healthy",
  "total_profiles": 51352619,
  ...
}
```

---

### Slow Queries

**Symptom:** Searches taking >5 seconds

**Causes:**
- Very broad keyword searches
- No filters applied
- Large result sets

**Solutions:**
1. Add country or industry filters
2. Be more specific with keywords
3. Add experience range filters

---

### S3 Connection Failed

**Error:** `S3 connectivity failed: HTTP 403`

**Fix:**

1. Check credentials in `.env`:
```bash
grep AWS_ .env
```

Should show:
```
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=ap-southeast-2
```

2. Rotate credentials if they were exposed (see `SECURITY.md` (same folder))

3. Test S3 connection:
```bash
./scripts/test_complete_setup.sh
```

---

## 📁 Project Structure

```
51M-Linkedin-user-DB/
├── backend/
│   ├── api/
│   │   └── duckdb_app.py      ← API server
│   └── duck.py                 ← DuckDB S3 queries
├── frontend/
│   ├── index.html              ← Search page
│   ├── results.html            ← Results page
│   ├── styles.css              ← Styling
│   ├── search.js               ← Search logic
│   ├── results.js              ← Results logic
│   └── README.md               ← Frontend docs
├── start_duckdb_api.sh         ← API startup script
├── .env                        ← Environment variables
└── QUICK_START.md              ← This file
```

---

## 🎯 Next Steps

### Option 1: Keep Using DuckDB Only (Current Setup)
- ✅ Zero disk usage
- ✅ Browse all 51M profiles
- ✅ Fast keyword + filter search
- ❌ No semantic search

**Perfect for:**
- Job boards
- Profile browsing
- Analytics dashboards
- Exact match searches

---

### Option 2: Add Selective Embeddings
- Load top 500K-1M profiles to PostgreSQL
- Generate embeddings for semantic search
- Keep DuckDB for browsing all 51M

**Disk needed:** ~20-30 GB
**Cost:** ~$10-20 for embeddings

**Adds:**
- ✅ "Find similar" features
- ✅ Semantic search ("AI expert" finds "ML researcher")
- ✅ Better relevance ranking

---

### Option 3: Full Embeddings (51M)
- Load all profiles to PostgreSQL
- Generate all embeddings

**Disk needed:** ~500-600 GB
**Cost:** ~$1,000 for embeddings

**Best for:** Professional semantic search platform

---

## 📖 More Documentation

- **Frontend Details:** `frontend/README.md`
- **Security Guide:** `SECURITY.md` (same folder)
- **Migration Guide:** `../architecture/HYBRID_SETUP.md`
- **API Docs:** http://localhost:8000/docs (when running)

---

## 💡 Tips

1. **Bookmark searches:** Copy the URL from results page (includes all filters)
2. **Export results:** Use browser extensions or build CSV export feature
3. **Customize limits:** Edit `search.js` to change results per page
4. **Add caching:** Results are fresh from S3 every time (no stale data)
5. **Monitor costs:** DuckDB queries S3 - monitor AWS data transfer costs

---

## ✅ System Status Checklist

- [ ] Docker PostgreSQL running (port 5433)
- [ ] Docker Redis running (port 6379)
- [ ] API server running (port 8000)
- [ ] Frontend accessible (file:// or http://localhost:3000)
- [ ] S3 connectivity working
- [ ] AWS credentials rotated (if exposed)

---

**Questions?** Check the logs:
- API: Terminal where you ran `start_duckdb_api.sh`
- Browser: F12 → Console tab

**Ready to search 51M profiles? Let's go! 🚀**
