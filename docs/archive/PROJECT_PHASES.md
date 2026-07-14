# INSIGHT - Project Phases & Test Cases

## Overview
This document breaks down the Semantic Talent Finder project into manageable phases with comprehensive test cases. Each phase follows the **Negative Spaces** philosophy to ensure bugs are immediately detectable.

---

## Phase 0: Foundation & Infrastructure Setup

### Objectives
- Set up Docker environment
- Initialize PostgreSQL with pgvector
- Create project structure
- Establish Git hooks
- Configure environment variables

### Deliverables
1. `docker-compose.yml` - PostgreSQL 17 + pgvector + optional Redis
2. `.env.example` - Template for environment variables
3. `.git/hooks/commit-msg` - AI attribution blocker
4. `.git/hooks/pre-push` - Commit count limiter
5. `requirements.txt` - Python dependencies
6. Project directory structure

### Test Cases - Phase 0

#### TC-0.1: Docker Container Health
```bash
# Test: PostgreSQL container starts and is healthy
docker compose up -d
docker compose ps

# Expected: postgres container status "healthy"
# Negative Space: Container exits or becomes "unhealthy"
```

#### TC-0.2: pgvector Extension Available
```sql
-- Test: pgvector extension can be created
\c semantic_talent
CREATE EXTENSION IF NOT EXISTS vector;
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Expected: vector extension present
-- Negative Space: Extension creation fails or not found
```

#### TC-0.3: Database Connection from Python
```python
# Test: Python can connect to PostgreSQL
import psycopg
from dotenv import load_dotenv
import os

load_dotenv()
dsn = os.getenv("PG_DSN")

try:
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
            assert "PostgreSQL 17" in version
            print(f"✅ Connected: {version}")
except Exception as e:
    raise RuntimeError(f"NEGATIVE SPACE VIOLATION: Cannot connect to DB: {e}")

# Expected: Successful connection, PostgreSQL 17
# Negative Space: Connection timeout, wrong version, auth failure
```

#### TC-0.4: Git Hooks Enforcement
```bash
# Test: commit-msg hook blocks AI attribution
git add .
git commit -m "test: something

Co-Authored-By: Claude <noreply@anthropic.com>"

# Expected: Commit rejected with error message
# Negative Space: Commit succeeds with AI attribution

# Test: pre-push hook blocks >100 commits
# (Simulate with 101 dummy commits)
# Expected: Push rejected
# Negative Space: Push succeeds with >100 commits
```

#### TC-0.5: Environment Variable Loading
```python
# Test: All required env vars are present
from dotenv import load_dotenv
import os

load_dotenv()

required_vars = [
    "PG_DSN", "PGUSER", "PGPASSWORD", "PGDATABASE", "PGHOST", "PGPORT"
]

missing = [v for v in required_vars if not os.getenv(v)]

if missing:
    raise EnvironmentError(
        f"NEGATIVE SPACE VIOLATION: Missing required env vars: {missing}"
    )

# Expected: All vars present
# Negative Space: Missing vars raise error
```

---

## Phase 1: Database Schema & Migrations

### Objectives
- Create staging and core tables
- Define indexes (vector HNSW, GIN, FTS, B-tree)
- Implement normalization tables (companies, experiences)
- Add CHECK constraints as negative spaces
- Create reset/migration scripts

### Deliverables
1. `migrations/001_schema.sql` - Full DDL
2. `migrations/002_indexes.sql` - Index definitions
3. `migrations/003_constraints.sql` - CHECK constraints
4. `data-pipeline/scripts/reset_db.py` - Database reset script
5. `docs/SCHEMA_REPORT.md` - ER diagram + rationale

### Test Cases - Phase 1

#### TC-1.1: Staging Table Creation
```sql
-- Test: staging_profiles_raw mirrors 62 CSV columns
CREATE TABLE staging_profiles_raw (
  "Full name" TEXT,
  "First Name" TEXT,
  -- ... 60 more columns
);

SELECT count(*) FROM information_schema.columns
WHERE table_name = 'staging_profiles_raw';

-- Expected: 62 columns
-- Negative Space: Column count mismatch
```

#### TC-1.2: Core Table Constraints
```sql
-- Test: profiles table enforces NOT NULL and CHECK constraints
INSERT INTO profiles (full_name, linkedin_username, years_experience)
VALUES ('', 'test_user', 5);

-- Expected: ERROR - CHECK constraint violation (empty full_name)
-- Negative Space: Insert succeeds with empty string

INSERT INTO profiles (full_name, linkedin_username, years_experience)
VALUES ('John Doe', 'test@invalid', 5);

-- Expected: ERROR - CHECK constraint violation (invalid username format)
-- Negative Space: Insert succeeds with invalid characters

INSERT INTO profiles (full_name, linkedin_username, years_experience)
VALUES ('John Doe', 'valid_user', 150);

-- Expected: ERROR - CHECK constraint violation (years_experience > 80)
-- Negative Space: Insert succeeds with impossible age
```

#### TC-1.3: Vector Dimension Enforcement
```sql
-- Test: embedding column only accepts 1536-dim vectors
INSERT INTO profiles (full_name, linkedin_username, embedding)
VALUES ('John Doe', 'john_doe', '[1,2,3]'::vector);

-- Expected: ERROR - dimension mismatch
-- Negative Space: Insert succeeds with wrong dimensions
```

#### TC-1.4: HNSW Index Creation
```sql
-- Test: HNSW index builds successfully
CREATE INDEX idx_profiles_embedding_hnsw
  ON profiles USING hnsw (embedding vector_cosine_ops)
  WITH (m=16, ef_construction=64);

SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'profiles' AND indexname = 'idx_profiles_embedding_hnsw';

-- Expected: Index present with correct parameters
-- Negative Space: Index missing or wrong parameters
```

#### TC-1.5: Foreign Key Cascade
```sql
-- Test: Deleting profile cascades to experiences
INSERT INTO profiles (id, full_name, linkedin_username)
VALUES ('550e8400-e29b-41d4-a716-446655440000', 'Test User', 'test_user');

INSERT INTO profile_experiences (profile_id, company_name, title)
VALUES ('550e8400-e29b-41d4-a716-446655440000', 'Test Co', 'Engineer');

DELETE FROM profiles WHERE id = '550e8400-e29b-41d4-a716-446655440000';

SELECT count(*) FROM profile_experiences
WHERE profile_id = '550e8400-e29b-41d4-a716-446655440000';

-- Expected: 0 experiences (cascaded delete)
-- Negative Space: Orphaned experiences remain
```

#### TC-1.6: Reset Script Idempotency
```python
# Test: reset_db.py can be run multiple times safely
import subprocess

for _ in range(3):
    result = subprocess.run(
        ["python", "data-pipeline/scripts/reset_db.py"],
        capture_output=True
    )
    assert result.returncode == 0, f"NEGATIVE SPACE: Reset failed: {result.stderr}"

# Expected: All runs succeed
# Negative Space: Second run fails or corrupts state
```

---

## Phase 2: Data Ingestion Pipeline

### Objectives
- Implement staging COPY (5,000 row batches)
- Build load-to-core transformation
- Parse and normalize fields (skills, geo, years)
- Handle duplicates (linkedin_username uniqueness)
- Implement skip_and_log for malformed rows

### Deliverables
1. `data-pipeline/ingestion/copy_to_staging.py`
2. `data-pipeline/ingestion/load_to_core.py`
3. `data-pipeline/ingestion/validators.py` - Field validation
4. `data-pipeline/ingestion/transformers.py` - Normalization logic
5. `tests/test_ingestion.py` - Unit tests

### Test Cases - Phase 2

#### TC-2.1: CSV to Staging COPY
```python
# Test: copy_to_staging.py loads CSV in 5k batches
import pandas as pd
import tempfile
import os

# Create test CSV with 12,000 rows
test_data = pd.DataFrame({
    "Full name": [f"Person {i}" for i in range(12000)],
    "LinkedIn Username": [f"user{i}" for i in range(12000)],
    # ... 60 more columns
})

with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
    test_data.to_csv(f.name, index=False)

    from data_pipeline.ingestion.copy_to_staging import run
    run(path=f.name, table='staging_profiles_raw')

# Verify row count
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM staging_profiles_raw;")
        count = cur.fetchone()[0]
        assert count == 12000, f"NEGATIVE SPACE: Expected 12000, got {count}"

os.unlink(f.name)

# Expected: 12,000 rows loaded in 3 batches
# Negative Space: Row count mismatch, batch failure
```

#### TC-2.2: Skills Parsing
```python
# Test: Skills column splits correctly
from data_pipeline.ingestion.transformers import parse_skills

test_cases = [
    ("Python, SQL, Docker", ["python", "sql", "docker"]),
    ("Python; SQL; Docker", ["python", "sql", "docker"]),
    ("Python,SQL,Docker", ["python", "sql", "docker"]),
    ("", []),
    (None, []),
    ("  Python  ,  SQL  ", ["python", "sql"]),
]

for input_val, expected in test_cases:
    result = parse_skills(input_val)
    assert result == expected, (
        f"NEGATIVE SPACE: parse_skills({input_val!r}) = {result}, expected {expected}"
    )

# Expected: All cases pass
# Negative Space: Parsing fails, wrong delimiter, case mismatch
```

#### TC-2.3: Years Experience Extraction
```python
# Test: Extract numeric years from messy strings
from data_pipeline.ingestion.transformers import parse_years_experience

test_cases = [
    ("5", 5),
    ("5 years", 5),
    ("10+", 10),
    ("3-5", 3),  # Take lower bound
    ("abc", None),
    ("", None),
    (None, None),
    ("150", None),  # Over 80 years - invalid
]

for input_val, expected in test_cases:
    result = parse_years_experience(input_val)
    assert result == expected, (
        f"NEGATIVE SPACE: parse_years_experience({input_val!r}) = {result}, expected {expected}"
    )

# Expected: All cases pass
# Negative Space: Invalid extractions, no bounds checking
```

#### TC-2.4: Duplicate Handling (UPSERT)
```python
# Test: load_to_core handles duplicate linkedin_username
import psycopg

# Insert initial record
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO staging_profiles_raw ("Full name", "LinkedIn Username", "Job title")
            VALUES ('John Doe', 'jdoe', 'Engineer')
        """)
    conn.commit()

from data_pipeline.ingestion.load_to_core import run
run()

# Insert duplicate with updated info
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO staging_profiles_raw ("Full name", "LinkedIn Username", "Job title")
            VALUES ('John Doe', 'jdoe', 'Senior Engineer')
        """)
    conn.commit()

run()

# Verify only one record exists with updated title
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT count(*), max(job_title)
            FROM profiles
            WHERE linkedin_username = 'jdoe'
        """)
        count, title = cur.fetchone()
        assert count == 1, f"NEGATIVE SPACE: Expected 1 record, got {count}"
        assert title == 'Senior Engineer', f"NEGATIVE SPACE: Title not updated"

# Expected: Single record with latest data
# Negative Space: Duplicate records or stale data
```

#### TC-2.5: Malformed Row Skipping
```python
# Test: Rows with missing required fields are skipped and logged
import logging
from io import StringIO

log_capture = StringIO()
handler = logging.StreamHandler(log_capture)
logger = logging.getLogger('data_pipeline.ingestion')
logger.addHandler(handler)
logger.setLevel(logging.WARNING)

# Insert rows with missing required fields
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO staging_profiles_raw ("Full name", "LinkedIn Username")
            VALUES
                (NULL, 'user1'),  -- Missing full_name
                ('User 2', NULL),  -- Missing linkedin_username
                ('User 3', 'user3')  -- Valid
        """)
    conn.commit()

from data_pipeline.ingestion.load_to_core import run
run()

# Verify only valid row loaded
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM profiles")
        count = cur.fetchone()[0]
        assert count == 1, f"NEGATIVE SPACE: Expected 1 valid row, got {count}"

# Verify warnings logged
log_output = log_capture.getvalue()
assert "Missing full_name" in log_output or "skipped" in log_output, \
    "NEGATIVE SPACE: Missing rows not logged"

# Expected: 1 row loaded, 2 skipped with warnings
# Negative Space: Invalid rows loaded or silent failures
```

#### TC-2.6: Geographic Field Mapping
```python
# Test: Location fields map correctly to core schema
test_row = {
    "Location": "Bangkok Metropolitan Area",
    "Locality": "Bangkok",
    "Region": "Bangkok",
    "Location Country": "Thailand"
}

from data_pipeline.ingestion.transformers import map_geo_fields

result = map_geo_fields(test_row)

assert result['location'] == "Bangkok Metropolitan Area"
assert result['locality'] == "Bangkok"
assert result['region'] == "Bangkok"
assert result['location_country'] == "Thailand"

# Test null handling
null_row = {"Location": None, "Locality": None, "Region": None, "Location Country": None}
result = map_geo_fields(null_row)
assert all(v is None for v in result.values()), \
    "NEGATIVE SPACE: NULL geo fields not preserved"

# Expected: Correct mapping, NULL preservation
# Negative Space: Field swap, NULL coercion to empty string
```

---

## Phase 3: Embedding Generation Pipeline

### Objectives
- Implement content template builder
- Add quality scoring (threshold enforcement)
- Batch processing (5k I/O, 100 embed)
- Exponential backoff retry logic
- Progress tracking with tqdm
- Skip_and_log for failed embeddings

### Deliverables
1. `data-pipeline/embeddings/generate.py`
2. `data-pipeline/embeddings/quality.py`
3. `data-pipeline/embeddings/retry.py`
4. `data-pipeline/embeddings/providers.py` - OpenAI/custom
5. `tests/test_embeddings.py`

### Test Cases - Phase 3

#### TC-3.1: Content Template Building
```python
# Test: build_content follows template exactly
from data_pipeline.embeddings.generate import build_content

test_row = {
    'job_title': 'Senior ML Engineer',
    'company_name': 'Tech Corp',
    'industry': 'Technology',
    'location': 'Bangkok, Thailand',
    'skills': ['python', 'nlp', 'pytorch']
}

result = build_content(test_row)

expected = "Professional: Senior ML Engineer at Tech Corp | Industry: Technology | Location: Bangkok, Thailand | Skills: python, nlp, pytorch"

assert result == expected, f"NEGATIVE SPACE: Template mismatch\nGot: {result}\nExpected: {expected}"

# Test NULL handling
null_row = {
    'job_title': None,
    'company_name': None,
    'industry': None,
    'location': None,
    'skills': None
}

result = build_content(null_row)
# Should not crash, should use defaults
assert "Professional:" in result, "NEGATIVE SPACE: Template broken with NULLs"

# Expected: Exact template match, graceful NULL handling
# Negative Space: Template deviation, NULL crashes
```

#### TC-3.2: Quality Score Calculation
```python
# Test: quality_score returns [0.0, 1.0]
from data_pipeline.embeddings.quality import quality_score

test_cases = [
    # (row, expected_score)
    (
        {'full_name': 'John', 'linkedin_username': 'john', 'job_title': 'Eng', 'industry': 'Tech'},
        1.0  # 0.3 + 0.3 + 0.2 + 0.2
    ),
    (
        {'full_name': 'John', 'linkedin_username': 'john', 'job_title': None, 'industry': None},
        0.6  # 0.3 + 0.3
    ),
    (
        {'full_name': None, 'linkedin_username': None, 'job_title': None, 'industry': None},
        0.0
    ),
]

for row, expected in test_cases:
    score = quality_score(row)

    # Negative space: score outside [0, 1]
    assert 0.0 <= score <= 1.0, f"NEGATIVE SPACE: score={score} outside [0, 1]"

    assert abs(score - expected) < 0.01, \
        f"NEGATIVE SPACE: Expected {expected}, got {score} for {row}"

# Expected: All scores in [0, 1], correct calculations
# Negative Space: Scores outside bounds, calculation errors
```

#### TC-3.3: Quality Threshold Filtering
```python
# Test: Only rows ≥ MIN_QUALITY are embedded
from data_pipeline.embeddings.generate import should_embed, MIN_QUALITY

# High quality
high_q = {
    'full_name': 'Jane Doe',
    'linkedin_username': 'jdoe',
    'job_title': 'Engineer',
    'industry': 'Tech'
}
assert should_embed(high_q), "NEGATIVE SPACE: High quality row rejected"

# Low quality (missing critical fields)
low_q = {
    'full_name': 'Jane Doe',
    'linkedin_username': 'jdoe',
    'job_title': None,
    'industry': None
}
# Quality = 0.6, if MIN_QUALITY=0.7
if MIN_QUALITY > 0.6:
    assert not should_embed(low_q), "NEGATIVE SPACE: Low quality row accepted"

# Expected: Threshold enforced
# Negative Space: Low quality rows embedded
```

#### TC-3.4: Exponential Backoff Retry
```python
# Test: Backoff increases exponentially and caps at 60s
from data_pipeline.embeddings.retry import backoff
import time

retries = [0, 1, 2, 3, 4, 5, 10]
expected_delays = [1, 2, 4, 8, 16, 32, 60]  # Cap at 60

for retry, expected in zip(retries, expected_delays):
    start = time.time()
    backoff(retry)
    elapsed = time.time() - start

    assert abs(elapsed - expected) < 0.1, \
        f"NEGATIVE SPACE: backoff({retry}) took {elapsed}s, expected ~{expected}s"

# Expected: Exponential growth, capped at 60s
# Negative Space: Linear backoff, no cap, wrong delays
```

#### TC-3.5: Batch Processing (5k/100)
```python
# Test: Batching logic splits correctly
from data_pipeline.embeddings.generate import batch_records

# Create 12,000 test records
records = [{'id': i, 'text': f'text {i}'} for i in range(12000)]

io_batches = list(batch_records(records, batch_size=5000))

assert len(io_batches) == 3, \
    f"NEGATIVE SPACE: Expected 3 I/O batches, got {len(io_batches)}"

# Verify sub-batching within I/O batch
embed_batches = list(batch_records(io_batches[0], batch_size=100))
assert len(embed_batches) == 50, \
    f"NEGATIVE SPACE: Expected 50 embed batches, got {len(embed_batches)}"

# Expected: Correct batch counts
# Negative Space: Wrong batch sizes, off-by-one errors
```

#### TC-3.6: Embedding Dimension Validation
```python
# Test: Generated embeddings are exactly 1536 dims
from data_pipeline.embeddings.providers import embed_many

test_texts = ["test text 1", "test text 2", "test text 3"]

embeddings = embed_many(test_texts)

assert len(embeddings) == 3, \
    f"NEGATIVE SPACE: Expected 3 embeddings, got {len(embeddings)}"

for i, emb in enumerate(embeddings):
    assert len(emb) == 1536, \
        f"NEGATIVE SPACE: Embedding {i} has {len(emb)} dims, expected 1536"

    # Verify numeric values
    assert all(isinstance(x, (int, float)) for x in emb), \
        f"NEGATIVE SPACE: Embedding {i} contains non-numeric values"

# Expected: 1536-dim numeric vectors
# Negative Space: Wrong dimensions, non-numeric values
```

#### TC-3.7: Progress Tracking
```python
# Test: tqdm progress bar updates correctly
from data_pipeline.embeddings.generate import run
from unittest.mock import patch
from tqdm import tqdm

with patch('data_pipeline.embeddings.generate.tqdm') as mock_tqdm:
    # Mock tqdm to capture calls
    mock_tqdm.return_value.__enter__ = lambda self: self
    mock_tqdm.return_value.__exit__ = lambda self, *args: None

    # Run with small dataset
    run()

    # Verify tqdm was called
    assert mock_tqdm.called, "NEGATIVE SPACE: Progress tracking not initialized"

# Expected: tqdm tracks progress
# Negative Space: Silent processing, no progress updates
```

---

## Phase 4: FastAPI Backend

### Objectives
- Implement hybrid search endpoint
- AsyncPG connection pooling
- NLU query parsing (optional microservice)
- Request/response models (Pydantic)
- Error handling with negative spaces
- Query parameter validation

### Deliverables
1. `api/app.py` - Main FastAPI app
2. `api/models.py` - Pydantic request/response models
3. `api/search.py` - Hybrid search logic
4. `api/nlu.py` - Query parsing (optional)
5. `api/database.py` - Connection pool management
6. `tests/test_api.py`

### Test Cases - Phase 4

#### TC-4.1: FastAPI Server Startup
```python
# Test: Server starts and health check passes
from fastapi.testclient import TestClient
from api.app import app

client = TestClient(app)

response = client.get("/health")
assert response.status_code == 200, \
    f"NEGATIVE SPACE: Health check failed with {response.status_code}"

data = response.json()
assert data['status'] == 'healthy', \
    f"NEGATIVE SPACE: Unhealthy status: {data}"

# Expected: 200 OK, healthy status
# Negative Space: 500 error, unhealthy status
```

#### TC-4.2: Connection Pool Initialization
```python
# Test: AsyncPG pool creates min/max connections
import asyncio
from api.database import get_pool

async def test_pool():
    pool = await get_pool()

    # Verify pool size
    assert pool.get_min_size() == 5, \
        f"NEGATIVE SPACE: Pool min size is {pool.get_min_size()}, expected 5"
    assert pool.get_max_size() == 40, \
        f"NEGATIVE SPACE: Pool max size is {pool.get_max_size()}, expected 40"

    # Test connection acquisition
    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT 1")
        assert result == 1, "NEGATIVE SPACE: Cannot execute query"

    await pool.close()

asyncio.run(test_pool())

# Expected: Pool configured correctly, connections work
# Negative Space: Wrong pool size, connection failures
```

#### TC-4.3: Pydantic Request Validation
```python
# Test: SearchRequest validates inputs
from api.models import SearchRequest
from pydantic import ValidationError

# Valid request
try:
    req = SearchRequest(
        text="ML engineer",
        embedding=[0.1] * 1536,
        limit=20,
        offset=0
    )
    assert req.limit == 20
except ValidationError as e:
    raise AssertionError(f"NEGATIVE SPACE: Valid request rejected: {e}")

# Invalid: wrong embedding dimension
try:
    req = SearchRequest(
        text="ML engineer",
        embedding=[0.1] * 100,  # Wrong size
        limit=20
    )
    raise AssertionError("NEGATIVE SPACE: Invalid embedding dimension accepted")
except ValidationError:
    pass  # Expected

# Invalid: negative limit
try:
    req = SearchRequest(
        text="ML engineer",
        embedding=[0.1] * 1536,
        limit=-10
    )
    raise AssertionError("NEGATIVE SPACE: Negative limit accepted")
except ValidationError:
    pass  # Expected

# Expected: Validation catches invalid inputs
# Negative Space: Invalid requests pass through
```

#### TC-4.4: Hybrid Search Query Execution
```python
# Test: /search endpoint returns results in <300ms
from fastapi.testclient import TestClient
from api.app import app
import time

client = TestClient(app)

request_body = {
    "text": "senior machine learning engineer",
    "embedding": [0.1] * 1536,
    "locality": "Bangkok",
    "country": "Thailand",
    "min_years": 5,
    "skills": ["python", "nlp"],
    "limit": 20,
    "offset": 0
}

start = time.time()
response = client.post("/search", json=request_body)
elapsed = (time.time() - start) * 1000  # ms

assert response.status_code == 200, \
    f"NEGATIVE SPACE: Search failed with {response.status_code}: {response.text}"

assert elapsed < 300, \
    f"NEGATIVE SPACE: Query took {elapsed}ms, expected <300ms"

results = response.json()
assert isinstance(results, list), \
    f"NEGATIVE SPACE: Expected list, got {type(results)}"

assert len(results) <= 20, \
    f"NEGATIVE SPACE: Returned {len(results)} results, limit was 20"

# Expected: <300ms, valid results, respects limit
# Negative Space: Slow query, wrong format, limit violation
```

#### TC-4.5: NULL Filter Handling
```python
# Test: NULL filters are ignored in WHERE clause
from fastapi.testclient import TestClient
from api.app import app

client = TestClient(app)

# Request with NULL filters
request_body = {
    "text": "engineer",
    "embedding": [0.1] * 1536,
    "locality": None,  # Should be ignored
    "country": None,
    "min_years": None,
    "skills": None,
    "limit": 10
}

response = client.post("/search", json=request_body)
assert response.status_code == 200, \
    f"NEGATIVE SPACE: NULL filters caused error: {response.text}"

# Should return results (not filtered out)
results = response.json()
assert len(results) >= 0, "NEGATIVE SPACE: NULL filters broke query"

# Expected: NULL filters ignored, query succeeds
# Negative Space: NULL causes crash or empty results
```

#### TC-4.6: SQL Injection Protection
```python
# Test: Parameterized queries prevent SQL injection
from fastapi.testclient import TestClient
from api.app import app

client = TestClient(app)

# Malicious input
request_body = {
    "text": "'; DROP TABLE profiles; --",
    "embedding": [0.1] * 1536,
    "locality": "Bangkok' OR '1'='1",
    "limit": 10
}

response = client.post("/search", json=request_body)

# Query should execute safely (not crash or return all results)
assert response.status_code == 200, \
    f"NEGATIVE SPACE: SQL injection caused error: {response.text}"

# Verify profiles table still exists
# (Would need DB check here)

# Expected: Malicious input treated as literal string
# Negative Space: SQL injection succeeds, table dropped
```

#### TC-4.7: Pagination Correctness
```python
# Test: Offset/limit pagination works correctly
from fastapi.testclient import TestClient
from api.app import app

client = TestClient(app)

base_request = {
    "text": "engineer",
    "embedding": [0.1] * 1536,
    "limit": 10
}

# Page 1
page1 = client.post("/search", json={**base_request, "offset": 0}).json()

# Page 2
page2 = client.post("/search", json={**base_request, "offset": 10}).json()

# Verify no overlap
page1_ids = {r['id'] for r in page1}
page2_ids = {r['id'] for r in page2}

overlap = page1_ids & page2_ids
assert len(overlap) == 0, \
    f"NEGATIVE SPACE: Pages overlap with {len(overlap)} common IDs"

# Expected: Distinct pages, no overlap
# Negative Space: Same results on both pages
```

---

## Phase 5: Testing & Quality Assurance

### Objectives
- Unit tests for all modules
- Integration tests for pipelines
- Load testing for query performance
- Chaos testing for failure scenarios
- Test coverage >80%

### Deliverables
1. `tests/unit/` - Unit tests
2. `tests/integration/` - Integration tests
3. `tests/load/` - Load tests (Locust/k6)
4. `tests/chaos/` - Failure injection tests
5. `pytest.ini` - Test configuration
6. Coverage report

### Test Cases - Phase 5

#### TC-5.1: Unit Test Coverage
```bash
# Test: >80% code coverage
pytest --cov=data_pipeline --cov=api --cov-report=term-missing

# Expected: Coverage >80%
# Negative Space: Coverage <80%, untested critical paths
```

#### TC-5.2: Integration Test - Full Pipeline
```python
# Test: CSV → Staging → Core → Embeddings → Search
import tempfile
import pandas as pd
from fastapi.testclient import TestClient

# 1. Create test CSV
test_data = pd.DataFrame({
    "Full name": ["Alice Smith", "Bob Jones"],
    "LinkedIn Username": ["alice_smith", "bob_jones"],
    "Job title": ["ML Engineer", "Data Scientist"],
    # ... other columns
})

with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
    test_data.to_csv(f.name, index=False)

    # 2. Import
    from data_pipeline.ingestion.copy_to_staging import run as copy_run
    copy_run(path=f.name, table='staging_profiles_raw')

    # 3. Load to core
    from data_pipeline.ingestion.load_to_core import run as load_run
    load_run()

    # 4. Generate embeddings
    from data_pipeline.embeddings.generate import run as embed_run
    embed_run()

    # 5. Search via API
    from api.app import app
    client = TestClient(app)

    response = client.post("/search", json={
        "text": "machine learning engineer",
        "embedding": [0.1] * 1536,
        "limit": 10
    })

    assert response.status_code == 200
    results = response.json()

    # Verify test data is searchable
    usernames = {r['linkedin_username'] for r in results}
    assert 'alice_smith' in usernames or 'bob_jones' in usernames, \
        "NEGATIVE SPACE: Ingested data not searchable"

# Expected: End-to-end pipeline works
# Negative Space: Any stage fails, data not queryable
```

#### TC-5.3: Load Test - 1000 Concurrent Queries
```python
# Using Locust for load testing
from locust import HttpUser, task, between

class SearchUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def search(self):
        self.client.post("/search", json={
            "text": "engineer",
            "embedding": [0.1] * 1536,
            "limit": 20
        })

# Run: locust -f tests/load/search_load.py --users 1000 --spawn-rate 100

# Expected:
# - P95 latency <300ms
# - P99 latency <500ms
# - 0% error rate
# Negative Space: >1% errors, latency spikes, connection pool exhaustion
```

#### TC-5.4: Chaos Test - Database Restart
```python
# Test: API handles DB reconnection gracefully
import docker
import time
from fastapi.testclient import TestClient
from api.app import app

client_docker = docker.from_env()
client_api = TestClient(app)

# Kill postgres container
container = client_docker.containers.get('stf-postgres')
container.restart()

time.sleep(5)  # Wait for restart

# API should reconnect
response = client_api.post("/search", json={
    "text": "engineer",
    "embedding": [0.1] * 1536,
    "limit": 10
})

assert response.status_code == 200, \
    f"NEGATIVE SPACE: API failed after DB restart: {response.text}"

# Expected: Graceful reconnection
# Negative Space: API crashes, connection errors persist
```

#### TC-5.5: Chaos Test - Embedding Service Timeout
```python
# Test: Embedding generation handles timeouts with backoff
from unittest.mock import patch, MagicMock
import time

with patch('data_pipeline.embeddings.providers.embed_many') as mock_embed:
    # Simulate timeout then success
    mock_embed.side_effect = [
        TimeoutError("API timeout"),
        TimeoutError("API timeout"),
        [[0.1] * 1536]  # Success on 3rd try
    ]

    from data_pipeline.embeddings.generate import embed_with_retry

    start = time.time()
    result = embed_with_retry(["test text"])
    elapsed = time.time() - start

    # Should have retried with backoff
    assert mock_embed.call_count == 3, \
        f"NEGATIVE SPACE: Expected 3 calls, got {mock_embed.call_count}"

    # Backoff: 1s + 2s = 3s minimum
    assert elapsed >= 3, \
        f"NEGATIVE SPACE: No backoff detected, elapsed={elapsed}s"

# Expected: Retry with backoff, eventual success
# Negative Space: Immediate failure, no retry, infinite loop
```

---

## Phase 6: Documentation & Deployment

### Objectives
- Complete schema report with ER diagrams
- API documentation (OpenAPI/Swagger)
- Deployment guide (Docker Compose)
- Performance tuning guide
- Monitoring setup

### Deliverables
1. `docs/SCHEMA_REPORT.md`
2. `docs/API_REFERENCE.md`
3. `docs/DEPLOYMENT.md`
4. `docs/PERFORMANCE_TUNING.md`
5. `docker-compose.production.yml`
6. `README.md` - Getting started guide

### Test Cases - Phase 6

#### TC-6.1: Docker Compose Production Mode
```bash
# Test: Production compose file starts all services
docker compose -f docker-compose.production.yml up -d

# Expected: All services healthy
# Negative Space: Container failures, port conflicts
```

#### TC-6.2: API Documentation Accessibility
```bash
# Test: Swagger UI available at /docs
curl http://localhost:8000/docs

# Expected: 200 OK, HTML response
# Negative Space: 404, docs not generated
```

#### TC-6.3: README Quick Start Works
```bash
# Test: Following README commands succeeds
# (Run as new user would)

git clone <repo>
cd <repo>
cp .env.example .env
docker compose up -d
# ... follow all README steps

# Expected: System operational
# Negative Space: Missing steps, errors, unclear instructions
```

---

## Negative Spaces Implementation Summary

### Key Principles Applied Across Phases

1. **Database Constraints**
   - CHECK constraints for field validation
   - NOT NULL for required fields
   - UNIQUE for natural keys
   - Foreign key cascades

2. **Python Type Contracts**
   - Pydantic models for API
   - Type hints everywhere
   - Runtime validation

3. **Explicit Boundaries**
   - Batch size limits
   - Timeout enforcement
   - Dimension validation
   - Quality thresholds

4. **Fail-Fast Assertions**
   - Pre/post-condition checks
   - Invariant validation
   - Range checks

5. **Error Context**
   - Custom exception classes
   - Context chains
   - Structured logging

6. **Observable State**
   - Progress tracking
   - Metric logging
   - Health checks

---

## Success Criteria

### Phase 0: Foundation
- [ ] Docker containers healthy
- [ ] Git hooks installed and tested
- [ ] Environment variables configured

### Phase 1: Schema
- [ ] All tables created with constraints
- [ ] Indexes built successfully
- [ ] Reset script idempotent

### Phase 2: Ingestion
- [ ] CSV imported in batches
- [ ] Transformations correct
- [ ] Duplicates handled
- [ ] Malformed rows skipped with logs

### Phase 3: Embeddings
- [ ] Quality threshold enforced
- [ ] Embeddings generated in batches
- [ ] Retry logic functional
- [ ] Progress visible

### Phase 4: API
- [ ] Server starts successfully
- [ ] Search returns results <300ms
- [ ] Pagination works
- [ ] Input validation functional

### Phase 5: Testing
- [ ] Unit test coverage >80%
- [ ] Integration tests pass
- [ ] Load tests meet targets
- [ ] Chaos tests demonstrate resilience

### Phase 6: Deployment
- [ ] Documentation complete
- [ ] Production compose functional
- [ ] README validated

---

**Last Updated**: 2025-10-07
**Status**: Planning Complete
