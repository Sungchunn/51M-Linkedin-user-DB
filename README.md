# INSIGHT - Talent Search

Search 51M+ LinkedIn profiles with fast semantic search.

## 🚀 Quick Start

### Option 1: Fast Search (Recommended)

Search 500K best profiles in <100ms:

```bash
# 1. Extract top profiles (15 min)
poetry run python3 scripts/extract_top_500k.py

# 2. Load to database (5 min)
poetry run load-parquet data/top_500k_profiles.parquet
poetry run load-core

# 3. Build indexes (30-45 min)
PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres \
  -d profiles -f sql/03_indexes.sql

# 4. Start API
./start_api.sh

# 5. Open frontend
open frontend/index.html
```

**Done!** Search 500K profiles with <100ms queries.

---

### Option 2: Analytics on All 51M

Browse entire dataset (slow but comprehensive):

```bash
# 1. Start DuckDB API
./start_duckdb_api.sh

# 2. Open frontend
open frontend/index.html
```

**Note:** Queries take 10-15 minutes (downloads 15GB from S3 each time).

---

## 📖 Full Guides

- **[HYBRID_SETUP.md](./HYBRID_SETUP.md)** - Complete setup instructions
- **[QUICK_START.md](./QUICK_START.md)** - Quick reference
- **[frontend/README.md](./frontend/README.md)** - Frontend docs
- **[docs/SECURITY.md](./docs/SECURITY.md)** - Security guide

---

## 💾 What You Need

- **Docker** (for PostgreSQL)
- **Python 3.11+** with Poetry
- **~21 GB disk space** (for Option 1)
- **42 GB available** ✅

---

## 🏗️ What You Get

### Fast Search (Option 1)
- 500K best profiles
- <100ms queries
- Keyword + filter search
- ~20 GB disk

### Analytics (Option 2)
- All 51M profiles
- 10-15 min queries
- Zero disk usage
- S3-based

---

## 🆘 Need Help?

- **Setup issues?** See `HYBRID_SETUP.md`
- **Frontend issues?** See `frontend/README.md`
- **Security?** See `docs/SECURITY.md`

---

## 📊 System Status

```bash
# Check everything is ready
./scripts/test_complete_setup.sh
```

---

**Current Status:** Ready to extract data!
**Next Step:** Run Option 1 or Option 2 above
