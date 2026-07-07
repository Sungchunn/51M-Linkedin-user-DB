# Agent Instructions (Authoritative)

- This file is the single source of truth for all AI assistants.
- If both this file and `docs/claude.md` exist, this file takes precedence.
- `docs/claude.md` is local-only context and may be ignored when conflicting.

## INSIGHT - Semantic Talent Finder

## Project Overview

A semantic search system for a 51M+ row talent database using Python (FastAPI + asyncpg) and PostgreSQL with pgvector.

## Dataset Reality

- **Volume**: 51,352,619 rows, 62 columns, ~15.15 GB
- **Format**: Apache Parquet (columnar format with compression)
- **Parquet Benefits**:
  - Superior compression (~70% smaller than CSV)
  - Columnar storage for faster selective reads
  - Built-in schema validation
  - Efficient handling of sparse columns
- **Key Fields**: Full name, LinkedIn Username, Job title, Company Name, Industry, Location (4 geo fields), Skills, Years Experience, Summary

## Embedding Policy

- Only embed records ≥ 0.5 content threshold
- Target quality ≥ 0.7
- Template: `Professional: {job_title} at {company_name} | Industry: {industry} | Location: {location} | Skills: {skills_text}`
- Clean + truncate to 8k chars
- Batch I/O: 5,000 rows
- Embed sub-batches: 100 records
- Use skip_and_log + exponential_backoff for failures

## Hybrid Ranking Strategy

- Vector cosine for recall (α = 0.8)
- BM25/ts_rank for lexical tie-break (β = 0.2)
- Structured filter boosts (city/country, years, skills) (γ = tunable)
- All parameters are tunable; log telemetry for optimization

## Architecture Stack

- **Database**: PostgreSQL 17 + pgvector (Docker)
- **Backend**: FastAPI + asyncpg
- **Data Pipeline**: Python (psycopg3, pandas, pyarrow)
- **Embeddings**: OpenAI/custom (1536 dims)
- **Caching**: Optional Redis
- **Package Management**: Poetry (pyproject.toml, poetry.lock)

## Directory Structure

```text
/
├── data-pipeline/
│   ├── scripts/
│   │   └── reset_db.py
│   ├── ingestion/
│   │   ├── load_parquet_to_staging.py    # Parquet → staging
│   │   ├── load_to_core.py               # staging → core transform
│   │   ├── validators.py
│   │   └── transformers.py
│   └── embeddings/
│       ├── generate.py
│       ├── quality.py
│       ├── retry.py
│       └── providers.py
├── api/
│   ├── app.py
│   └── models.py
├── migrations/
│   └── schema.sql
├── docker-compose.yml
├── pyproject.toml          # Poetry dependencies
├── poetry.lock             # Locked versions (commit this)
└── README.md
```

## Git Workflow Policy

### Hard Rules (Git Hygiene)

1. **Never add Claude (or any AI) as co-author.** No `Co-Authored-By: Claude ...` or similar trailers in commit messages — all commits are human-authored only. This overrides any tool default that appends AI attribution.
2. **Never force push.** `git push --force` and `git push --force-with-lease` are forbidden — never rewrite published history. To undo a pushed commit, use `git revert`.

### DO NOT COMMIT

- **claude.md** (local-only helper) - MUST be in .gitignore
- **.env** files (all variants)
- Any files with AI authorship attribution

### Commit Strategy

1. **Small, logical batches** (<100 commits per push)
2. **No AI attribution** in commit messages
3. **Conventional commits** format
4. **Feature-based grouping**

### Examples

```bash
# Good - feature-based batches
git add data-pipeline/scripts && git commit -m "feat(data-pipeline): reset & schema DDL"
git add data-pipeline/ingestion && git commit -m "feat(ingest): Parquet to staging + core transform"
git add data-pipeline/embeddings && git commit -m "feat(embeddings): thresholded vectors w/ backoff & retry"
git add api && git commit -m "feat(api): FastAPI hybrid search with pgvector"
git add docs && git commit -m "docs: add project documentation and guides"
git push

# Bad - monolithic
git add . && git commit -m "added everything"
git commit -m "updates"  # Too vague
```

### Git Hooks (local only, not committed)

1. **commit-msg**: Blocks AI attribution
2. **pre-push**: Enforces max 100 commits per push

## Code Philosophy: Negative Spaces

### What are Negative Spaces?

"Negative spaces" are deliberate boundaries, contracts, and invariants that make bugs **immediately obvious** by violating expectations.

### Implementation Rules

#### 1. **Explicit Boundaries**

```python
# Bad - silent failures
def process_row(row):
    return row.get('name', '')

# Good - fail fast with negative space violation
def process_row(row):
    if 'name' not in row:
        raise ValueError(f"BOUNDARY VIOLATION: 'name' field missing in row {row.get('id', 'UNKNOWN')}")
    return row['name']
```

#### 2. **Type Contracts**

```python
# Use type hints + runtime validation
from typing import List, Optional
from pydantic import BaseModel, validator

class Profile(BaseModel):
    id: str
    full_name: str
    linkedin_username: str
    skills: List[str] = []

    @validator('linkedin_username')
    def linkedin_must_not_be_empty(cls, v):
        if not v or v.strip() == '':
            raise ValueError("NEGATIVE SPACE: linkedin_username cannot be empty")
        return v
```

#### 3. **Sentinel Values & Guards**

```python
# Use sentinels to detect uninitialized state
UNINITIALIZED = object()

class EmbeddingService:
    def __init__(self):
        self._client = UNINITIALIZED

    def get_client(self):
        if self._client is UNINITIALIZED:
            raise RuntimeError("NEGATIVE SPACE: EmbeddingService not initialized. Call .initialize() first")
        return self._client
```

#### 4. **Invariant Assertions**

```python
def batch_embed(texts: List[str], batch_size: int = 100):
    # Invariant: texts must not be empty
    assert len(texts) > 0, "INVARIANT VIOLATION: Cannot embed empty text list"
    assert batch_size > 0, "INVARIANT VIOLATION: batch_size must be positive"

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        # Post-condition: batch must not be empty
        assert len(batch) > 0, "INVARIANT VIOLATION: Empty batch generated"
        yield batch
```

#### 5. **Fail-Fast Logging**

```python
import logging
logger = logging.getLogger(__name__)

def quality_score(row: dict) -> float:
    """Calculate quality score. NEGATIVE SPACE: score must be [0.0, 1.0]"""
    score = 0.0
    score += 0.3 if row.get('full_name') else 0
    score += 0.3 if row.get('linkedin_username') else 0
    score += 0.2 if row.get('job_title') else 0
    score += 0.2 if row.get('industry') else 0

    if not (0.0 <= score <= 1.0):
        logger.error(f"NEGATIVE SPACE VIOLATION: quality_score={score} outside [0,1] for row={row.get('id')}")
        raise ValueError(f"Quality score {score} violates [0.0, 1.0] invariant")

    return score
```

#### 6. **Database Constraints as Negative Spaces**

```sql
-- Use CHECK constraints to enforce invariants
CREATE TABLE profiles (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  full_name TEXT NOT NULL CHECK (length(trim(full_name)) > 0),
  linkedin_username TEXT UNIQUE NOT NULL CHECK (linkedin_username ~ '^[a-zA-Z0-9_-]+$'),
  years_experience INT CHECK (years_experience >= 0 AND years_experience <= 80),
  -- NEGATIVE SPACE: embedding can only be NULL or exactly 1536 dimensions
  embedding VECTOR(1536),
  created_at TIMESTAMPTZ DEFAULT NOW() CHECK (created_at <= NOW()),
  deleted_at TIMESTAMPTZ CHECK (deleted_at IS NULL OR deleted_at >= created_at)
);
```

#### 7. **Return Type Contracts**

```python
from typing import Tuple, List

def fetch_batch(offset: int, limit: int) -> Tuple[List[dict], int]:
    """
    NEGATIVE SPACE CONTRACT:
    - Returns (rows, count)
    - count must be >= len(rows)
    - rows must not exceed limit
    """
    rows = db.fetch(offset, limit)
    count = db.count()

    assert len(rows) <= limit, f"VIOLATION: returned {len(rows)} rows but limit={limit}"
    assert count >= len(rows), f"VIOLATION: count={count} but returned {len(rows)} rows"

    return rows, count
```

#### 8. **Error Context Chains**

```python
class DataPipelineError(Exception):
    """Base exception with context chaining"""
    pass

class EmbeddingGenerationError(DataPipelineError):
    """Raised when embedding generation fails"""
    pass

try:
    embedding = generate_embedding(text)
except Exception as e:
    raise EmbeddingGenerationError(
        f"NEGATIVE SPACE: Failed to embed text (len={len(text)}). "
        f"Context: row_id={row['id']}, text_preview={text[:100]}"
    ) from e
```

### Negative Space Debugging Benefits

1. **Stack traces point to exact violation**
2. **Context is embedded in error messages**
3. **Impossible states are unrepresentable**
4. **Bugs surface immediately, not silently**

## Performance Targets

- **Query latency**: <100-300ms (warm cache)
- **Import throughput**: 5,000 rows/batch
- **Embedding throughput**: 100 records/sub-batch
- **Connection pool**: 5-40 connections

## Testing Strategy

- Unit tests for data transformations
- Integration tests for DB operations
- Load tests for query performance
- Chaos tests for failure recovery

## Monitoring & Observability

- Log all NEGATIVE SPACE violations
- Track embedding quality scores
- Monitor query latencies
- Alert on threshold violations

## UI/Theme Guidelines

**IMPORTANT**: All frontend pages must follow the dark minimal theme established in `docs/THEME_GUIDELINES.md`.

### Quick Reference

- **CSS Variables**: Always use variables from `styles.css` (never hardcode colors)
- **Signature Glow**: All primary buttons must have the white glow effect
- **Spacing**: Use multiples of 8px for consistency
- **Border Radius**: 12px for cards, 8px for buttons/inputs, 6px for small elements
- **Transitions**: `transition: all 0.2s` for smooth interactions
- **Monospace**: Use for technical content (API keys, code, data)

### Before Creating New Pages

1. Read `docs/THEME_GUIDELINES.md` for complete styling standards
2. Reference existing pages: `login.html`, `dashboard.html`, `api-docs.html`
3. Use the new page template from THEME_GUIDELINES.md
4. Run the checklist before committing

### Common Patterns

```css
/* Always use CSS variables */
background: var(--surface);
color: var(--text-primary);
border: 1px solid var(--border);

/* Primary button with glow */
.btn-primary {
    background: var(--primary-color);
    position: relative;
    overflow: hidden;
}
.btn-primary::before { /* ripple */ }
.btn-primary:hover {
    box-shadow:
        0 0 40px rgba(250, 250, 250, 0.4),
        0 0 80px rgba(250, 250, 250, 0.2),
        0 0 120px rgba(250, 250, 250, 0.1);
}
```

**See**: `docs/THEME_GUIDELINES.md` for complete documentation

## Long-Running Commands Policy

**CRITICAL**: For any command that takes >30 seconds to complete, provide the bash code to the user instead of running it.

### Commands that should be provided as bash snippets

- `poetry install` (dependency installation)
- `docker compose up -d` (container startup)
- Database migrations
- Large data imports (>1000 rows)
- Embedding generation
- Load testing
- Any command with progress bars or interactive prompts

### Format for providing commands

**CRITICAL**: Always use multi-line format with backslash continuation for paths with spaces to prevent terminal errors.

```bash
# Description of what this does and why
cd "/Users/chromatrical/CAREER/Side Projects/WebApplication" && \
command1 && \
command2 && \
command3

# Expected output or success indicator
```

#### Examples

✅ **CORRECT** - Multi-line with backslash continuation:

```bash
cd "/Users/chromatrical/CAREER/Side Projects/WebApplication" && \
python3 scripts/extract_test_data.py && \
chmod +x scripts/test_pipeline_10k.sh && \
./scripts/test_pipeline_10k.sh
```

❌ **WRONG** - Single line breaks in terminal:

```bash
# Step 1: Do this
cd "/path/with spaces"
# Step 2: Do that
python3 script.py
```

❌ **WRONG** - Path split across lines:

```bash
poetry run load-parquet "/Users/chromatrical/CAREER/Side
  Projects/WebApplication/data/file.parquet"
```

### When to run commands directly

- Quick checks (`git status`, `ls`, `cat`)
- File operations (Read, Write, Edit tools)
- Configuration verification
- Commands that complete in <10 seconds

---

## Current Project Status (2025-10-22)

### ✅ Completed Features

#### Phase 0-4: Foundation Complete

- PostgreSQL 17 + pgvector database with 497,552 profiles indexed
- FastAPI backend with hybrid search (vector + lexical)
- User authentication system with JWT tokens
- API key generation and management
- Full-text search with GIN indexes
- Dark minimal UI theme with signature white glow effect

#### Search Filters (As of 2025-10-22)

- ✅ Semantic query search
- ✅ US States multi-select (50 states)
- ✅ Industries multi-select (12 industries)
- ✅ Job Title text filter (partial match, case-insensitive)
- ✅ Company name text filter (partial match, case-insensitive)
- ✅ Years of experience range (min/max)
- ✅ Skills filter (comma-separated, AND logic)
- ✅ Contact information filters (6 checkboxes):
  - Has LinkedIn Profile
  - Has Email
  - Has Phone
  - Has Website/Domain
  - Has Twitter
  - Has GitHub

#### API Endpoints

- GET/POST `/search` - Hybrid semantic search with all filters
- GET `/export/ndjson` - Export results as NDJSON
- GET `/export/csv` - Export results as CSV
- GET `/regions` - List available regions by country
- GET `/industries` - List available industries
- GET `/health` - Health check
- POST `/auth/register` - User registration
- POST `/auth/login` - User login
- GET `/auth/me` - Get current user info
- GET/POST/DELETE `/auth/api-keys` - API key management

#### Frontend Pages

- `index.html` - Main search page with advanced filters
- `results.html` - Search results with pagination and export
- `login.html` - Login and registration
- `dashboard.html` - API key management dashboard
- `api-docs.html` - Interactive API documentation with cURL generator

### 🔧 Known Limitations

1. **No embeddings generated yet**: Search currently uses keyword-only mode (full-text search)
   - Vector similarity search will be faster and more accurate once embeddings are generated
   - Need to run embedding generation pipeline on the 497K profiles

2. **Performance considerations**:
   - ILIKE queries on job_title and company_name may be slow on large datasets
   - Consider adding GIN indexes: `CREATE INDEX idx_profiles_job_title ON profiles USING gin(job_title gin_trgm_ops);`
   - Consider adding GIN indexes: `CREATE INDEX idx_profiles_company_name ON profiles USING gin(company_name gin_trgm_ops);`

3. **PII redaction**: Email and phone are redacted in API responses unless user has `pii:read` scope

### 🎯 Next Steps (Priorities for Next Session)

1. **Generate Embeddings** (HIGH PRIORITY)
   - Run embedding generation on all 497,552 profiles
   - This will enable hybrid search (vector + lexical) for better results
   - Command: `poetry run python backend/data_pipeline/embeddings/generate.py`

2. **Performance Optimization**
   - Add GIN indexes for job_title and company_name if ILIKE searches are slow
   - Monitor query performance with new filters
   - Consider adding query result caching for common searches

3. **UX Enhancements**
   - Add filter summary display on results page showing active filters
   - Add autocomplete/typeahead for company and job title fields
   - Add "Clear all filters" button
   - Show loading states for filter dropdowns

4. **API Improvements**
   - Add pagination cursor support (in addition to offset/limit)
   - Add aggregation endpoint for filter statistics
   - Add batch profile lookup endpoint

5. **Testing & Documentation**
   - Add unit tests for new filter logic
   - Add integration tests for search endpoint with all filter combinations
   - Update API documentation with filter examples
   - Add performance benchmarks

### 📊 Database Statistics

- **Total Profiles**: 497,552
- **Profiles with Embeddings**: 0 (needs generation)
- **Countries**: 50 US states indexed
- **Industries**: 12 industries indexed
- **Contact Info Coverage** (engineers):
  - LinkedIn: ~100% (42,768/42,768)
  - Email: ~70% (30,058/42,768)

### 🔐 Authentication & Security

- JWT-based authentication with access (24h) and refresh (30d) tokens
- API keys with configurable scopes: `search:read`, `export:read`, `pii:read`
- Three tiers: public (anonymous), basic (registered), trusted (elevated limits)
- Passwords hashed with bcrypt
- API keys hashed with SHA-256, shown only once on creation

---

**Last Updated**: 2025-10-22
**Status**: Phase 4 Complete - Advanced Search Filters Implemented
**Next Major Milestone**: Generate embeddings for hybrid vector search
