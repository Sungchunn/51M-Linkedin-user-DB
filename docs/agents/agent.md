# Agent Instructions (Authoritative)

- This file is the single source of truth for all AI assistants.
- If both this file and `docs/claude.md` exist, this file takes precedence.
- `docs/claude.md` is local-only context and may be ignored when conflicting.

# INSIGHT - Semantic Talent Finder

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
```
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

## Long-Running Commands Policy

**CRITICAL**: For any command that takes >30 seconds to complete, provide the bash code to the user instead of running it.

### Commands that should be provided as bash snippets:
- `poetry install` (dependency installation)
- `docker compose up -d` (container startup)
- Database migrations
- Large data imports (>1000 rows)
- Embedding generation
- Load testing
- Any command with progress bars or interactive prompts

### Format for providing commands:

**CRITICAL**: Always use multi-line format with backslash continuation for paths with spaces to prevent terminal errors.

```bash
# Description of what this does and why
cd "/Users/chromatrical/CAREER/Side Projects/WebApplication" && \
command1 && \
command2 && \
command3

# Expected output or success indicator
```

**Examples:**

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

### When to run commands directly:
- Quick checks (`git status`, `ls`, `cat`)
- File operations (Read, Write, Edit tools)
- Configuration verification
- Commands that complete in <10 seconds

---

**Last Updated**: 2025-10-07
**Status**: Phase 0 - Foundation Setup

