# INSIGHT - Semantic Talent Finder

A high-performance semantic search system for a 51M+ row talent database using Python (FastAPI + asyncpg) and PostgreSQL with pgvector.

## 📊 Project Overview

- **Dataset**: 51,352,619 profiles, 62 columns, ~15.15 GB (Apache Parquet format)
- **Stack**: PostgreSQL 17 + pgvector, FastAPI, asyncpg, Python 3.11+
- **Goal**: <300ms hybrid semantic search with plain-English queries
- **Philosophy**: [Negative Spaces](./docs/NEGATIVE_SPACES_GUIDE.md) - bugs are immediately detectable

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- 16GB+ RAM (for dataset processing)
- ~20GB disk space

### 1. Clone & Setup

```bash
git clone <repository-url>
cd WebApplication

# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env
```

### 2. Start Infrastructure

```bash
# Start PostgreSQL + pgvector
docker compose up -d

# Verify containers are healthy
docker compose ps
```

### 3. Install Python Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Initialize Database

```bash
# Run migrations
python data-pipeline/scripts/reset_db.py

# Verify schema
psql $PG_DSN -c "\dt"
```

### 5. Import Data

```bash
# Stage: Parquet → staging table (columnar batch loading)
python data-pipeline/ingestion/load_parquet_to_staging.py \
  --parquet /path/to/profiles.parquet \
  --table staging_profiles_raw

# Transform: staging → core (typed, validated)
python data-pipeline/ingestion/load_to_core.py

# Verify import
psql $PG_DSN -c "SELECT count(*) FROM profiles;"
```

### 6. Generate Embeddings

```bash
# Generate embeddings (respects quality thresholds)
python data-pipeline/embeddings/generate.py

# Monitor progress (batches of 5k I/O, 100 embed)
# Expected: ~6-8 hours for 51M rows
```

### 7. Start API Server

```bash
# Development
uvicorn api.app:app --reload --host 0.0.0.0 --port 8000

# Production
gunicorn -k uvicorn.workers.UvicornWorker -w 4 api.app:app
```

### 8. Test Search

```bash
# Health check
curl http://localhost:8000/health

# Search
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "text": "senior ML engineer in Bangkok, Python + NLP, 5+ years",
    "embedding": [0.1, ...],  # 1536 dims
    "locality": "Bangkok",
    "country": "Thailand",
    "min_years": 5,
    "skills": ["python", "nlp"],
    "limit": 20
  }'
```

## 📁 Project Structure

```
/
├── data-pipeline/
│   ├── scripts/
│   │   └── reset_db.py                    # Database reset utility
│   ├── ingestion/
│   │   ├── load_parquet_to_staging.py     # Parquet → staging (5k batches)
│   │   ├── load_to_core.py                # staging → core transform
│   │   ├── validators.py                  # Field validation
│   │   └── transformers.py                # Normalization logic
│   └── embeddings/
│       ├── generate.py                    # Embedding pipeline
│       ├── quality.py                     # Quality scoring
│       ├── retry.py                       # Exponential backoff
│       └── providers.py                   # OpenAI/custom clients
├── api/
│   ├── app.py                       # FastAPI application
│   ├── models.py                    # Pydantic schemas
│   ├── search.py                    # Hybrid search logic
│   ├── database.py                  # AsyncPG pool management
│   └── nlu.py                       # Query parsing (optional)
├── migrations/
│   ├── 001_schema.sql               # Core schema DDL
│   ├── 002_indexes.sql              # Index definitions
│   └── 003_constraints.sql          # CHECK constraints
├── tests/
│   ├── unit/                        # Unit tests
│   ├── integration/                 # Integration tests
│   ├── load/                        # Load tests (Locust)
│   └── chaos/                       # Failure injection tests
├── docs/
│   ├── SCHEMA_REPORT.md             # ER diagram + rationale
│   ├── INDEX_REPORT.md              # Index analysis
│   ├── API_REFERENCE.md             # API documentation
│   ├── DEPLOYMENT.md                # Production deployment guide
│   └── PERFORMANCE_TUNING.md        # Optimization tips
├── .git/hooks/
│   ├── commit-msg                   # AI attribution blocker
│   └── pre-push                     # Commit count limiter
├── docker-compose.yml               # Development environment
├── docker-compose.production.yml    # Production environment
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment template
├── .gitignore                       # Git ignore rules
└── README.md                        # This file
```

## 🧪 Testing

### Run All Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Coverage report
pytest --cov=data_pipeline --cov=api --cov-report=html
```

### Load Testing

```bash
# Install Locust
pip install locust

# Run load test (1000 concurrent users)
locust -f tests/load/search_load.py --users 1000 --spawn-rate 100
```

### Chaos Testing

```bash
# Database restart resilience
python tests/chaos/test_db_restart.py

# Embedding service timeout handling
python tests/chaos/test_embedding_timeout.py
```

## 📚 Documentation

- **[Project Phases](./docs/PROJECT_PHASES.md)**: Detailed breakdown of 6 phases with test cases
- **[Negative Spaces Guide](./docs/NEGATIVE_SPACES_GUIDE.md)**: Programming philosophy for bug prevention
- **[Schema Report](./docs/SCHEMA_REPORT.md)**: Database design rationale
- **[API Reference](./docs/API_REFERENCE.md)**: Endpoint documentation
- **[Performance Tuning](./docs/PERFORMANCE_TUNING.md)**: Optimization guide

## 🏗️ Architecture

### Data Flow

```
Parquet File (15GB, columnar)
    ↓
[Staging Table] ← Batch load (5k rows, pyarrow)
    ↓
[Core Tables] ← Typed transform + validation
    ↓
[Embedding Generation] ← Quality filtering (≥0.7)
    ↓
[pgvector HNSW Index] ← Vector search ready
    ↓
[FastAPI Search] ← Hybrid ranking (<300ms)
```

**Why Parquet?**
- 70% smaller than CSV with compression
- Columnar format enables selective column reads
- Built-in schema validation
- Faster batch processing with pyarrow
- Native support in pandas/polars

### Hybrid Search Strategy

```python
score = (α × vector_cosine) + (β × ts_rank) + (γ × structured_boosts)
#        0.8                  0.2             tunable
```

- **Vector**: HNSW approximate nearest neighbor (recall)
- **Lexical**: Full-text search with ts_rank (precision)
- **Filters**: City, country, years, skills (structured)

## 🔧 Configuration

### Environment Variables

```bash
# Database
PG_DSN="host=localhost port=5432 dbname=semantic_talent user=postgres password=postgres"
PGUSER=postgres
PGPASSWORD=postgres
PGDATABASE=semantic_talent
PGHOST=127.0.0.1
PGPORT=5432

# Embedding Service
OPENAI_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536

# API
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Pipeline
BATCH_SIZE_IO=5000
BATCH_SIZE_EMBED=100
MIN_QUALITY_SCORE=0.7
MAX_TEXT_LENGTH=8000
```

### Docker Compose

```yaml
# docker-compose.yml
services:
  postgres:
    image: pgvector/pgvector:pg17
    environment:
      POSTGRES_DB: semantic_talent
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports: ["5432:5432"]
    volumes:
      - stf_pgdata:/var/lib/postgresql/data
```

## 🎯 Performance Targets

| Metric | Target | Actual |
|--------|--------|--------|
| Query Latency (P95) | <300ms | TBD |
| Query Latency (P99) | <500ms | TBD |
| Import Throughput | 5k rows/batch | TBD |
| Embedding Throughput | 100 records/batch | TBD |
| Database Connections | 5-40 pool | ✅ |
| Test Coverage | >80% | TBD |

## 🐛 Debugging with Negative Spaces

This project follows the **Negative Spaces** philosophy:

- **Fail fast** at boundaries with clear errors
- **Assert invariants** in critical calculations
- **Type contracts** with runtime validation
- **Database constraints** enforce data integrity
- **Structured logging** with full context

Example:
```python
def quality_score(row: dict) -> float:
    """INVARIANT: result must be in [0.0, 1.0]"""
    score = 0.0
    score += 0.3 if row.get('full_name') else 0
    score += 0.3 if row.get('linkedin_username') else 0
    score += 0.2 if row.get('job_title') else 0
    score += 0.2 if row.get('industry') else 0

    if not (0.0 <= score <= 1.0):
        raise AssertionError(
            f"INVARIANT VIOLATION: quality_score={score} outside [0.0, 1.0]. "
            f"Row: {row.get('id')}"
        )
    return score
```

See [NEGATIVE_SPACES_GUIDE.md](./docs/NEGATIVE_SPACES_GUIDE.md) for details.

## 🔒 Git Workflow

### Local Files (NEVER commit)

- `docs/claude.md` - AI context (in .gitignore)
- `.env*` - Secrets
- `*.csv`, `*.parquet` - Data files

### Commit Strategy

```bash
# Small, logical batches
git add data-pipeline/scripts
git commit -m "feat(data-pipeline): reset & schema DDL"

git add data-pipeline/ingestion
git commit -m "feat(ingest): staging COPY + core transform"

git add api
git commit -m "feat(api): FastAPI hybrid search endpoint"

# Push in batches (<100 commits)
git push
```

### Git Hooks (installed locally)

```bash
# Install hooks
chmod +x .git/hooks/commit-msg
chmod +x .git/hooks/pre-push

# commit-msg: Blocks AI attribution
# pre-push: Enforces <100 commits per push
```

## 📈 Monitoring

### Health Check

```bash
curl http://localhost:8000/health

# Expected:
# {
#   "status": "healthy",
#   "database": "connected",
#   "pool_size": 5
# }
```

### Logs

```bash
# API logs
tail -f logs/api.log

# Pipeline logs
tail -f logs/pipeline.log

# Database logs
docker compose logs -f postgres
```

### Metrics (optional)

- Prometheus: Query latency, error rates
- Grafana: Dashboards for performance
- Sentry: Error tracking

## 🚢 Deployment

### Production Checklist

- [ ] Environment variables configured (`.env.production`)
- [ ] Database backups automated
- [ ] Connection pool sized (min=10, max=100)
- [ ] HNSW index parameters tuned (`ef_search=64`)
- [ ] API workers scaled (4-8 per instance)
- [ ] Logging configured (structured JSON)
- [ ] Monitoring enabled (Prometheus + Grafana)
- [ ] SSL/TLS certificates installed
- [ ] Rate limiting enabled
- [ ] CORS configured

### Docker Compose Production

```bash
docker compose -f docker-compose.production.yml up -d
```

See [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) for full guide.

## 🤝 Contributing

1. Follow [Negative Spaces](./docs/NEGATIVE_SPACES_GUIDE.md) philosophy
2. Write tests for new features
3. Keep commits small and logical
4. No AI attribution in commits
5. Maintain >80% test coverage

## 📄 License

[Your License Here]

## 🙋 Support

- **Documentation**: See `/docs` directory
- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **Questions**: [Discussions](https://github.com/your-repo/discussions)

## 🎓 Learning Resources

- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

---

**Status**: Phase 0 - Foundation Setup
**Last Updated**: 2025-10-07
**Next Phase**: Database Schema & Migrations ([PROJECT_PHASES.md](./docs/PROJECT_PHASES.md))
