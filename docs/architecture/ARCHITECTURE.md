# PROSPECTIQ (INSIGHT) — System Architecture

**Last Updated:** 2026-07-14
**Status:** ~497K profiles served locally; full 51.35M-row dataset partitioned on S3 (cold-tier foundation built)

---

## Executive Summary

PROSPECTIQ is a semantic talent-search platform over scraped LinkedIn profiles. A local
PostgreSQL 17 + pgvector instance serves ~497K profiles through a FastAPI backend and a
vanilla-JS frontend. The full 51M-row parquet dataset lives on S3 and has been reshaped
into a state-partitioned Parquet warehouse (queryable via Athena/DuckDB) as the
foundation of a tiered hot/cold architecture — see
[NEXT_STEPS_ARCHITECTURE.md](./NEXT_STEPS_ARCHITECTURE.md) for the active roadmap.

**Key facts:**

- **Loaded locally:** 497,552 profiles in the `profiles` table
- **Embeddings:** 0 of 497K generated — search currently runs as full-text only
  (the hybrid path silently falls back to `keyword_search()` when no embeddings exist)
- **Cold tier:** `s3://sungchunn-linkedin-db/curated/usa_profiles/state=<state>/` —
  52 partitions (50 states + DC + `other`), 51,352,619 rows, built via Athena CTAS
- **Stack:** FastAPI + asyncpg (raw SQL, no ORM), PostgreSQL 17 + pgvector (Docker,
  external port **5433**), vanilla JS frontend (no framework, no build step), Poetry

---

## Three FastAPI Apps — Don't Confuse Them

The repo contains three separate FastAPI applications on two schema lineages:

| App | Entry point | Purpose | Storage |
|-----|-------------|---------|---------|
| **Main product API** | `backend/api/app.py` (`./start_api.sh`) | Search, export, auth, stats over the local `profiles` table | Postgres `profiles` (migrations 001–009), asyncpg |
| **Hybrid rebuild** | `backend/app.py` (`make api/start`) | Hot-tier serving + Redis cache + DuckDB analytics | Postgres `profiles_hot`/`profiles_detail` (from `sql/`), psycopg, Redis, DuckDB-over-S3 |
| **DuckDB browse API** | `backend/api/duckdb_app.py` (`./start_duckdb_api.sh`) | Zero-local-storage browse/search of the full 51M parquet on S3 | DuckDB httpfs only — read-only, no indexes, no auth |

Everything below describes the **main product API** unless stated otherwise. The hybrid
track is documented in [HYBRID_SETUP.md](./HYBRID_SETUP.md) and
[REBUILD_SUMMARY.md](./REBUILD_SUMMARY.md).

---

## Request Path (Main API)

```
Static frontend (:5500)          FastAPI (:8000)              PostgreSQL 17 + pgvector (:5433)
 vanilla JS pages      ──HTTP──►  backend/api/app.py  ──────►  profiles table
 config.js picks API base        global asyncpg pool           GIN FTS + HNSW vector indexes
```

- `frontend/config.js` selects the API base URL by hostname (localhost →
  `http://localhost:8000`, otherwise same-origin or a `<meta name="api-url">` tag).
- CORS is configured from env (`CORS_ORIGINS`, `CORS_ORIGIN_REGEX`, `DEV_RELAX_CORS`)
  and only tightens when `ENVIRONMENT=production`.

### Backend module map (`backend/api/`)

- **`app.py`** — entrypoint. Lifespan creates/closes the connection pool, seeds an admin
  user, configures CORS. Endpoints: `/search`, `/export/csv`, `/export/ndjson`,
  `/stats`, `/health`, `/regions`, `/industries`, plus `/auth/*` routes.
- **`database.py`** — module-level asyncpg pool singleton (`PG_DSN`, `DB_POOL_MIN/MAX`,
  `DB_TIMEOUT`).
- **`search.py`** — `hybrid_search()` checks whether any embeddings exist; if none, or
  if the embedding provider fails, it falls back to `keyword_search()` (full-text only).
  Hybrid score = **0.8 × vector cosine + 0.2 × ts_rank**. Filters are appended as
  numbered asyncpg params (`$1`, `$2`, …) — parameter-index ordering bugs have happened
  here before; be careful when adding filters.
- **`models.py`** — Pydantic request/response models.
- **`auth.py` / `auth_routes.py` / `jwt_utils.py` / `user_manager.py`** — see Auth below.

### Search behavior

Filters available on `/search`: query text, regions, industries, job title, company
(both ILIKE partial match), experience range, skills, and `has_*` contact-presence
filters (LinkedIn, email, phone, website, Twitter, GitHub).

---

## Two Coexisting Auth Systems

1. **Env-var API keys** (`auth.py`): the `API_KEYS` env var holds a JSON map of
   key → `{scopes, tier}`. `resolve_auth_context()` produces an `AuthContext` with
   scopes (`search:read`, `export:read`, `pii:read`) and tiers
   (`public`/`basic`/`trusted`) that gate max result limit and offset.
2. **DB-backed users + JWT** (`auth_routes.py`, schema in
   `migrations/008_users_and_api_keys.sql`): registration/login, bcrypt passwords,
   24h access / 30d refresh tokens, SHA-256-hashed API keys managed from
   `frontend/dashboard.html`. Database-issued keys are wired into
   `resolve_auth_context()` for tier-based access (fixed in commit `70bfdb0`).

**PII redaction** (email/phone hidden without `pii:read`) exists but is currently
**disabled via `temp:` commits** — check `git log` before assuming its state.

---

## Database

**Connection:** Docker Compose, external port **5433**, database `profiles`,
user/pass `postgres`. Redis on 6379; pgweb on 8081 with `--profile tools`.

### Migration lineage (`migrations/`, run in order — this is what the API queries)

| Migration | Adds |
|-----------|------|
| `001_extensions.sql` | pgvector, pg_trgm, uuid-ossp |
| `002_staging_table.sql` | `staging_profiles_raw` (62 TEXT columns mirroring the parquet) |
| `003_core_schema.sql` | `profiles` + `companies`, `profile_experiences`, `profile_education`, `profile_certifications` (28 CHECK constraints) |
| `004_indexes.sql` | HNSW (m=16, ef_construction=64), GIN FTS, GIN skills, B-tree filter indexes |
| `005_data_completeness.sql` | `data_completeness_pct` 0–100 score + index |
| `006_optimize_filter_indexes.sql` | Filter-index tuning |
| `007_add_search_vector.sql` | Generated `search_vector` tsvector column + GIN index |
| `008_users_and_api_keys.sql` | `users`, `api_keys`, `refresh_tokens`, `audit_log` |
| `009_performance_optimizations_10m.sql` | 10M-scale prep, incl. a state-partitioned `profiles_partitioned` experiment |

Schema details and rationale: [../database/SCHEMA_REPORT.md](../database/SCHEMA_REPORT.md).
Index strategy: [../database/INDEX_REPORT.md](../database/INDEX_REPORT.md).

### Alternate schema lineage (`sql/` — hybrid track only)

`sql/01–05` define the two-tier `profiles_hot` / `profiles_detail` schema used by
`backend/app.py`, `jobs/promote_hot.py`, and `embeddings/batch_embed.py`. The main API
does not use it.

---

## Data Pipeline (`backend/data_pipeline/`)

**Flow:** parquet → staging (`ingestion/load_parquet_to_staging.py`) →
transform/validate → core `profiles` (`ingestion/load_to_core.py`).

Three loader tiers (see [INGESTION_ARCHITECTURE.md](./INGESTION_ARCHITECTURE.md)):

1. `load_incremental.py` — simple, in-memory dedup, ~1–2K rows/s
2. `load_optimized.py` — COPY-based, DB-driven dedup, ~5–10K rows/s
3. `cloud_worker.py` — distributed S3/SQS/Redis workers (code complete, not deployed)

`embeddings/generate.py` batch-embeds profiles meeting the quality threshold with
OpenAI `text-embedding-3-small` (1536 dims). Policy, template, and batch sizes are
specified in [`agent.md`](../../agent.md). Dataset-prep utilities
(`prepare_best_1m_dataset.py`, `prepare_best_10m_dataset.py`, …) live in `scripts/`.

Entry points (from `pyproject.toml`): `poetry run reset-db`, `load-parquet`,
`load-core`, `generate-embeddings`.

---

## Cold Tier: S3 + Athena Warehouse (built 2026-07)

The full dataset (`s3://sungchunn-linkedin-db/USA_filtered.parquet`, 15.2 GB,
51,352,619 rows, 99.9% US) was reshaped server-side via Athena CTAS into:

```
s3://sungchunn-linkedin-db/curated/usa_profiles/state=<state>/   # 52 partitions
```

- Partition key is **`state`** (from `Region`) — profiling showed it is the clean key
  (2.3% null, even spread) vs `Company Industry` (49% null), so implementation
  deviates from the country/industry recommendation in
  [NEXT_STEPS_ARCHITECTURE.md](./NEXT_STEPS_ARCHITECTURE.md).
- Cleaning during CTAS: 56 columns → snake_case, `years_experience` → int
  (out-of-range → null), `Region` → US-state whitelist else `other`.
- Athena external table `insight.profiles_raw`; IAM user `insight-s3-reader` with
  inline policy `insight-athena-reshape`.
- Not yet wired into any API — next steps are precomputed aggregates and a query
  router (hot Postgres vs cold DuckDB/Athena).

---

## Frontend

Plain JS/HTML/CSS in `frontend/` — no framework, no build step. Pages share
`styles.css` (CSS variables) and `auth.js`:

- `index.html` + `search.js` — search form and filters
- `results.html` + `results.js` — results table, pagination, CSV export
- `login.html`, `dashboard.html` (API key management), `api-docs.html`

All styling must follow
[../guides/THEME_GUIDELINES.md](../guides/THEME_GUIDELINES.md): dark minimal theme,
CSS variables only (never hardcode colors), white-glow primary buttons, 8px spacing
grid.

---

## Testing, Tooling, Conventions

- **Tests:** `poetry run pytest backend/tests/` (phase 0–4 suites; require `PG_DSN`
  in `.env`, otherwise they skip). Coverage on by default.
- **Lint/format/typecheck:** ruff, black, mypy (line length 100).
- **SQL safety:** always asyncpg `$N` placeholders; explicit column lists; no `SELECT *`.
- **Philosophy:** fail-fast invariants and explicit boundaries — see
  [../guides/NEGATIVE_SPACES_GUIDE.md](../guides/NEGATIVE_SPACES_GUIDE.md).
- **Git:** conventional commits, no AI attribution trailers, never force-push.

---

## Deployment

Deployment configs exist for Railway (`railway.json`), Render (`render.yaml`),
Fly.io (`fly.toml`), plus a multi-stage `Dockerfile` and `Procfile`. Nothing is
deployed to production yet. See
[../deployment/DEPLOYMENT_GUIDE.md](../deployment/DEPLOYMENT_GUIDE.md) and
[../deployment/SCALING_TO_51M_GUIDE.md](../deployment/SCALING_TO_51M_GUIDE.md).

---

## What Changed vs the October 2025 Version of This Doc

- Added: auth systems, export endpoints, migrations 005–009, the three-app split,
  the S3/Athena cold tier, and the tiered-warehouse roadmap pointer.
- Removed: speculative Vue.js migration, ECS/EMR bulk-load plans (superseded by the
  tiered hot/cold approach), and stale per-date metrics.
- Corrected: hybrid search currently runs keyword-only (0 embeddings generated);
  Postgres external port is 5433, not 5432.
