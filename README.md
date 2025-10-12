# INSIGHT - LinkedIn Talent Search Platform

**Search 497K+ LinkedIn profiles with lightning-fast queries and rich data.**

Perfect for GTM teams, recruiters, and sales prospecting with Claygent integration.

---

## 🎯 What You Get

### **Current Status: PRODUCTION READY** ✅

- **497,552 profiles** loaded in PostgreSQL
- **<1 second queries** with full-text search
- **15 rich data columns** including summary, social links, contact info
- **CSV export** for up to 10,000 results
- **Web UI** with advanced filters and pagination

### **Data Fields (15 columns)**
- First Name, Last Name, Job Title, Company, Industry
- Location, Years Experience, Professional Summary
- LinkedIn, Email, Phone, Website, Twitter, GitHub
- Skills (array)

---

## 🚀 Quick Start

### **Prerequisites**
- Docker (for PostgreSQL)
- Python 3.11+ with Poetry
- ~21 GB disk space available

### **1. Start the System**

```bash
# Start PostgreSQL + API
./start_api.sh

# Open web interface
open frontend/index.html
```

**That's it!** The system is already loaded with 497K profiles.

### **2. Search & Export**

1. Enter keywords: "software engineer", "data scientist", "marketing manager"
2. Apply filters: country, industry, experience, skills
3. View results with full summaries and contact info
4. Export to CSV (up to 10,000 rows)

---

## 📊 System Architecture

### **Current Setup (Local)**
```
┌─────────────────┐
│  Web Frontend   │ ← Vanilla JS, no dependencies
│  (HTML/JS/CSS)  │
└────────┬────────┘
         │ POST /search
         ↓
┌─────────────────┐
│   FastAPI       │ ← Python async API
│   (Port 8000)   │
└────────┬────────┘
         │ AsyncPG
         ↓
┌─────────────────┐
│  PostgreSQL 17  │ ← 497K profiles, full-text search
│  (Docker)       │    Query time: 500-1000ms
└─────────────────┘
```

### **Database Schema**
- **profiles** table: 34 columns, GIN indexes for full-text search
- **Indexes**: Full-text (name, title, summary), location, industry, skills
- **Search**: Keyword-based full-text search with filters

---

## 🔧 Features

### ✅ Implemented
- [x] PostgreSQL database with 497K profiles
- [x] FastAPI search API with filters
- [x] Web UI with horizontal scrolling tables
- [x] Full-text search across name, title, company, summary
- [x] Filter by: country, industry, experience, skills
- [x] CSV export (up to 10K rows)
- [x] 15 data columns including social profiles
- [x] Pagination (20/50/100 per page)
- [x] <1s query performance

### 🚧 Planned (Scaling to 51M Profiles)
- [ ] Cloud deployment (AWS/Railway)
- [ ] Incremental data loading pipeline
- [ ] Vector search with embeddings (semantic search)
- [ ] Auto-scaling infrastructure
- [ ] CDN for frontend assets
- [ ] API rate limiting & authentication

---

## 📈 Scaling Plan

### **Phase 1: Current (Local Development)** ✅
- **Data**: 497K profiles
- **Storage**: ~5 GB PostgreSQL
- **Performance**: 500-1000ms queries
- **Cost**: $0 (local)

### **Phase 2: Cloud Deployment (1M Profiles)**
- **Infrastructure**: Railway/Render PostgreSQL
- **Data**: Import 1M best profiles
- **Storage**: ~10 GB database
- **Performance**: <500ms queries
- **Cost**: ~$20-50/month

### **Phase 3: Production Scale (10M+ Profiles)**
- **Infrastructure**: AWS (RDS + EC2/ECS)
- **Data**: 10M-51M profiles with incremental loading
- **Storage**: Managed PostgreSQL (50-100 GB)
- **Features**: Vector search, caching, CDN
- **Performance**: <200ms queries with Redis cache
- **Cost**: ~$100-300/month

---

## 🚀 Deployment Options

### **Option 1: Railway (Easiest)** ⭐ Recommended for Phase 2
```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login & init
railway login
railway init

# 3. Add PostgreSQL
railway add postgresql

# 4. Deploy API
railway up
```

**Pros**: One-click PostgreSQL, auto-scaling, easy setup
**Cons**: ~$20-50/month for 1M profiles
**Best for**: Quick MVP, small-medium datasets

### **Option 2: AWS (Most Scalable)** For Phase 3
```bash
# Infrastructure as Code
terraform apply -var-file=production.tfvars
```

**Pros**: Full control, auto-scaling, enterprise-grade
**Cons**: More complex setup, higher cost
**Best for**: 10M+ profiles, production use

### **Option 3: Render** Alternative to Railway
Similar to Railway but with more free tier options.

---

## 💾 Data Loading Strategy

### **Current: Local PostgreSQL (497K profiles)**
```bash
# Already done! Data is loaded.
# Location: PostgreSQL Docker container
# Size: ~5 GB
```

### **Three-Tier Ingestion Architecture**

We have three ingestion strategies optimized for different scales:

#### **Tier 1: Simple Loader (Current - <1M profiles)** ✅
- **Use case**: Local development, initial setup
- **Performance**: 1,000-2,000 rows/sec (~15 min for 1M)
- **Memory**: 2-4 GB
- **Best for**: Getting started, testing

```bash
# Extract 1M dataset
poetry run python3 scripts/prepare_1m_dataset.py

# Load with deduplication
poetry run python -m backend.data_pipeline.ingestion.load_incremental \
  data/USA_1M_test.parquet
```

#### **Tier 2: Optimized Loader (1M-2M profiles)** ⚡ NEW
- **Use case**: Faster local loading before cloud deployment
- **Performance**: 5,000-10,000 rows/sec (~2-3 min for 1M)
- **Memory**: <500 MB (uses database for deduplication)
- **Best for**: Rapid iteration, larger local datasets

```bash
# Optimized loader with database-driven deduplication
poetry run python -m backend.data_pipeline.ingestion.load_optimized \
  data/USA_1M_test.parquet

# 5x faster than Tier 1!
# No RAM bottleneck - uses PostgreSQL COPY protocol
```

**Key optimizations:**
- Database-driven deduplication (no RAM cache)
- PostgreSQL COPY protocol (10x faster than INSERT)
- Streaming Parquet reader (low memory footprint)
- Temporary staging table for batch processing

#### **Tier 3: Cloud Worker (10M-51M profiles)** ☁️ PRODUCTION
- **Use case**: Cloud deployment, full 51M dataset
- **Performance**: 50,000-100,000 rows/sec (~15 min for 51M)
- **Architecture**: Distributed workers + Redis + S3
- **Best for**: Production scale, regular updates

```bash
# Deploy cloud ingestion workers (ECS Fargate)
# See docs/INGESTION_ARCHITECTURE.md for full guide

# Workers automatically:
# 1. Poll SQS queue for chunk jobs
# 2. Stream Parquet from S3 (no full download)
# 3. Use Redis bloom filter for deduplication
# 4. Write to PostgreSQL RDS with COPY protocol
# 5. Report progress to coordinator API
```

**Cost for 51M profiles:**
- One-time ingestion: ~$12
- Monthly incremental updates: ~$0.25

### **Decision Matrix**

| Dataset Size | Recommended Tier | Load Time | Memory | Use Case |
|-------------|------------------|-----------|--------|----------|
| <1M         | Tier 1 (Simple)  | 15 min    | 2-4 GB | Initial setup |
| 1M-2M       | Tier 2 (Optimized) | 2-3 min | <500 MB | Fast local iteration |
| 10M-51M     | Tier 3 (Cloud)   | 10-15 min | Distributed | Production |

### **Documentation**
- **[docs/INGESTION_ARCHITECTURE.md](./docs/INGESTION_ARCHITECTURE.md)** - Complete architecture guide
- **[docs/SCALING_PLAN.md](./docs/SCALING_PLAN.md)** - Cloud deployment strategy

---

## 🧪 API Endpoints

### **Search Profiles**
```bash
POST /search
{
  "query": "software engineer",
  "location_country": "united states",
  "industry": "computer software",
  "min_years_experience": 5,
  "limit": 100,
  "offset": 0
}
```

### **Get Statistics**
```bash
GET /stats
# Returns: total profiles, countries, industries
```

### **Health Check**
```bash
GET /health
# Returns: database status, profile count
```

---

## 🔐 Security Notes

⚠️ **IMPORTANT**: This dataset contains scraped LinkedIn data. Before deploying:

1. **Review data source legality** in your jurisdiction
2. **Implement authentication** for production API
3. **Add rate limiting** to prevent abuse
4. **Use environment variables** for all credentials
5. **Enable HTTPS** for production deployment
6. **Comply with GDPR/privacy laws** if serving EU users

See `docs/SECURITY.md` for details.

---

## 🛠️ Development

### **Project Structure**
```
.
├── backend/
│   ├── api/              # FastAPI application
│   │   ├── app.py        # Main API server
│   │   ├── models.py     # Pydantic models
│   │   ├── search.py     # Search logic
│   │   └── database.py   # DB connection pool
│   └── data_pipeline/    # Data ingestion
│       └── ingestion/    # Parquet loaders
├── frontend/             # Web UI
│   ├── index.html        # Search page
│   ├── results.html      # Results display
│   ├── search.js         # Search logic
│   ├── results.js        # Results rendering
│   └── styles.css        # Styling
├── migrations/           # SQL migrations
├── scripts/              # Utility scripts
└── docker-compose.yml    # PostgreSQL setup
```

### **Run Tests**
```bash
poetry run pytest backend/tests/ -v
```

### **Check Data Quality**
```bash
poetry run python3 scripts/check_data_quality.py
```

---

## 📚 Documentation

- **[HYBRID_SETUP.md](./HYBRID_SETUP.md)** - Complete setup guide
- **[QUICK_START.md](./QUICK_START.md)** - Quick reference
- **[docs/INGESTION_ARCHITECTURE.md](./docs/INGESTION_ARCHITECTURE.md)** - Three-tier ingestion strategy ⭐ NEW
- **[docs/SCALING_PLAN.md](./docs/SCALING_PLAN.md)** - Cloud deployment & scaling
- **[docs/PHASE_STATUS.md](./docs/PHASE_STATUS.md)** - Implementation progress
- **[docs/SECURITY.md](./docs/SECURITY.md)** - Security considerations

---

## 🎯 Use Cases

### **For GTM Teams**
- Build targeted prospect lists by title, industry, location
- Export to CSV for import into CRM (HubSpot, Salesforce)
- Enrich leads with professional summaries via Claygent
- Find decision makers at specific companies

### **For Recruiters**
- Search by skills, experience, location
- Find candidates with specific tech stacks
- Export candidate lists for outreach
- View full LinkedIn profiles and contact info

### **For Data Scientists**
- Analyze talent markets by geography
- Track skill trends across industries
- Build ML models on professional data
- Research career progression patterns

---

## 🔄 Recent Updates

### **Latest (2025-10-11)**
- ✅ Added First Name & Last Name columns
- ✅ Added professional Summary field
- ✅ CSV export functionality (10K row limit)
- ✅ Actual URL display for LinkedIn/Website
- ✅ 15 total columns with social profiles
- ✅ 497K profiles loaded and indexed

### **Previous**
- FastAPI backend with PostgreSQL
- Full-text search with GIN indexes
- Web UI with horizontal scrolling
- Filter by country, industry, experience, skills

---

## 🤝 Contributing

This is a personal project. For questions or suggestions, please open an issue.

---

## 📄 License

This project is for educational and personal use only. The LinkedIn data is subject to LinkedIn's Terms of Service. Use responsibly and in compliance with applicable laws.

---

**Current Status:** ✅ **Production Ready (497K Profiles)**
**Next Step:** Deploy to cloud or scale to 1M+ profiles

**Questions?** Check the docs or run `./scripts/test_complete_setup.sh`
