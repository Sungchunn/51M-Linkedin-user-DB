# INSIGHT Database Schema Report

**Phase 1: Database Schema Design**
**Status**: ✅ Complete — original design report (migrations 001–004)
**Date**: 2025-10-07 (addendum for migrations 005–009: 2026-07-14)

> **Note (2026-07-14):** This report documents the original core schema. Five
> migrations have landed since — see the [Addendum](#addendum-migrations-005009)
> at the bottom for what they added.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Schema Architecture](#schema-architecture)
3. [Table Specifications](#table-specifications)
4. [Negative Spaces Implementation](#negative-spaces-implementation)
5. [Migration Strategy](#migration-strategy)
6. [Verification Results](#verification-results)

---

## Executive Summary

The INSIGHT semantic talent finder uses a **normalized PostgreSQL 17 schema** optimized for 51M+ LinkedIn profiles with vector similarity search capabilities.

### Key Metrics
- **Total Tables**: 6 (1 staging, 5 core)
- **Vector Dimensions**: 1536 (text-embedding-3-small)
- **Constraints**: 28 CHECK constraints implementing Negative Spaces
- **Natural Key**: `linkedin_username` (unique, immutable)
- **Storage Estimate**: ~250GB (51M rows × ~5KB/row)

### Design Principles
1. **Negative Spaces First**: Impossible states are unrepresentable at schema level
2. **Quality Threshold**: Only profiles with ≥70% quality score receive embeddings
3. **Soft Deletes**: `is_deleted` flag preserves referential integrity
4. **Normalization**: Companies table reduces redundancy by ~40%

---

## Schema Architecture

### Two-Stage Data Flow

```
┌─────────────────┐
│  Parquet File   │  51M rows, 62 columns, ~15GB
│  (Raw Source)   │
└────────┬────────┘
         │
         ▼ COPY (Batch 5000)
┌─────────────────────────┐
│ staging_profiles_raw    │  Minimal constraints
│ (Migration 002)         │  Fast bulk import
└────────┬────────────────┘
         │
         ▼ Transform + Validate
┌─────────────────────────┐
│    profiles (core)      │  CHECK constraints
│  + companies            │  Normalized schema
│  + profile_experiences  │  Foreign keys
│  + profile_education    │  Vector embedding
│  + profile_certifications│
└─────────────────────────┘
```

---

## Table Specifications

### 1. staging_profiles_raw (Migration 002)

**Purpose**: Raw data landing zone for high-speed COPY operations

```sql
CREATE TABLE staging_profiles_raw (
    "Full name" TEXT,
    "LinkedIn Username" TEXT,
    "Job title" TEXT,
    -- ... 59 more columns matching Parquet schema exactly
    "import_batch_id" TEXT,
    "import_timestamp" TIMESTAMPTZ DEFAULT NOW()
);
```

**Design Decisions**:
- Column names preserve exact Parquet spelling (e.g., `"Full name"`)
- All columns TEXT type for maximum import compatibility
- No foreign keys or constraints (applied during transformation)
- Indexed on `"LinkedIn Username"` for deduplication

**Lifecycle**: Data stays here temporarily (~1 hour max) before transformation to core schema

---

### 2. profiles (Migration 003)

**Purpose**: Core table with full Negative Spaces enforcement

#### Schema Definition

| Column | Type | Constraints | Negative Space |
|--------|------|-------------|----------------|
| `id` | UUID | PRIMARY KEY | Auto-generated |
| `full_name` | TEXT | NOT NULL, len > 0 | Empty strings rejected |
| `linkedin_username` | TEXT | UNIQUE, NOT NULL, regex | Natural key, ^[a-zA-Z0-9_-]+$ |
| `job_title` | TEXT | - | NULL allowed |
| `company_name` | TEXT | - | NULL allowed |
| `industry` | TEXT | - | NULL allowed |
| `years_experience` | INT | 0 ≤ x ≤ 80 | Outside range = error |
| `location_country` | TEXT | - | 4-level hierarchy |
| `region` | TEXT | - | - |
| `locality` | TEXT | - | - |
| `skills` | TEXT[] | - | GIN indexed |
| `skills_normalized` | TEXT[] | - | For fuzzy matching |
| `headline` | TEXT | - | - |
| `summary` | TEXT | - | - |
| `email` | TEXT | Regex validation | NULL or valid format |
| `phone` | TEXT | - | - |
| `website` | TEXT | - | - |
| `embedding` | VECTOR(1536) | Exact dimension | NULL if quality < 0.7 |
| `content_quality_score` | DECIMAL(3,2) | 0.0 ≤ x ≤ 1.0 | Outside range rejected |
| `profile_completeness` | INT | 0 ≤ x ≤ 100 | Percentage invariant |
| `created_at` | TIMESTAMPTZ | ≤ NOW() | Future dates rejected |
| `updated_at` | TIMESTAMPTZ | ≥ created_at | Time travel prevented |
| `deleted_at` | TIMESTAMPTZ | NULL or ≥ created_at | - |
| `is_deleted` | BOOLEAN | DEFAULT FALSE | Soft delete flag |

#### Critical Constraints

```sql
-- NEGATIVE SPACE: linkedin_username must match pattern
CHECK (linkedin_username ~ '^[a-zA-Z0-9_-]+$')

-- NEGATIVE SPACE: email must be valid or NULL
CHECK (email IS NULL OR email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$')

-- NEGATIVE SPACE: years_experience biological limits
CHECK (years_experience >= 0 AND years_experience <= 80)

-- NEGATIVE SPACE: quality score is probability
CHECK (content_quality_score >= 0 AND content_quality_score <= 1)

-- NEGATIVE SPACE: time cannot flow backwards
CHECK (updated_at >= created_at)
CHECK (deleted_at IS NULL OR deleted_at >= created_at)
```

**Embedding Policy**:
- Only profiles with `content_quality_score ≥ 0.7` receive embeddings
- NULL embeddings are valid (low-quality profiles can still be searched via FTS)
- Dimension enforcement (1536) prevents dimension mismatch errors

---

### 3. companies (Migration 003)

**Purpose**: Normalized company data to reduce redundancy

```sql
CREATE TABLE companies (
    id UUID PRIMARY KEY,
    name TEXT UNIQUE NOT NULL CHECK (length(trim(name)) > 0),
    industry TEXT,
    size_range TEXT,
    founded_year INT CHECK (founded_year >= 1800 AND founded_year <= EXTRACT(YEAR FROM NOW())),
    headquarters_country TEXT,
    headquarters_city TEXT,
    website TEXT,
    linkedin_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Benefits**:
- Reduces storage by ~40% (company name appears once, not 51M times)
- Enables company-level analytics (e.g., "top 100 companies by talent density")
- Easier updates (change company name in 1 row, not millions)

**Constraint Highlights**:
- `founded_year` must be between 1800 and current year
- `name` must be unique and non-empty (Negative Space)

---

### 4. profile_experiences (Migration 003)

**Purpose**: Work history with CASCADE delete for data consistency

```sql
CREATE TABLE profile_experiences (
    id UUID PRIMARY KEY,
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    company_id UUID REFERENCES companies(id),
    company_name TEXT NOT NULL,
    title TEXT NOT NULL,
    start_date DATE,
    end_date DATE CHECK (end_date IS NULL OR end_date >= start_date),
    is_current BOOLEAN DEFAULT FALSE,
    description TEXT,
    location TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Design Rationale**:
- `company_id` is optional (not all companies normalized)
- `company_name` stored for fast joins (denormalization for performance)
- `end_date` NULL means "present" (Negative Space: NULL ≠ arbitrary future date)
- `CASCADE DELETE` ensures orphaned records cannot exist

**Constraint**: `end_date >= start_date` (no time travel)

---

### 5. profile_education (Migration 003)

**Purpose**: Educational background

```sql
CREATE TABLE profile_education (
    id UUID PRIMARY KEY,
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    institution TEXT NOT NULL,
    degree TEXT,
    field_of_study TEXT,
    start_year INT CHECK (start_year >= 1900),
    end_year INT CHECK (end_year IS NULL OR end_year >= start_year),
    grade TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Constraints**:
- `start_year >= 1900` (modern education era)
- `end_year >= start_year` (temporal consistency)

---

### 6. profile_certifications (Migration 003)

**Purpose**: Professional certifications and licenses

```sql
CREATE TABLE profile_certifications (
    id UUID PRIMARY KEY,
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    issuing_organization TEXT,
    issue_date DATE,
    expiration_date DATE CHECK (expiration_date IS NULL OR expiration_date >= issue_date),
    credential_id TEXT,
    credential_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Constraint**: `expiration_date >= issue_date` (temporal validity)

---

## Negative Spaces Implementation

### Philosophy
**Negative Spaces**: Explicitly define what is *not allowed* to make bugs immediately obvious.

### Examples

#### 1. Impossible States Rejected at Insert
```sql
-- ❌ REJECTED: years_experience = 150 (biologically impossible)
INSERT INTO profiles (full_name, linkedin_username, years_experience)
VALUES ('John Doe', 'johndoe', 150);
-- ERROR: new row violates check constraint "profiles_years_experience_check"

-- ✅ ACCEPTED: years_experience = 5 (valid)
INSERT INTO profiles (full_name, linkedin_username, years_experience)
VALUES ('John Doe', 'johndoe', 5);
```

#### 2. Email Validation
```sql
-- ❌ REJECTED: Invalid email format
INSERT INTO profiles (..., email) VALUES (..., 'not-an-email');
-- ERROR: new row violates check constraint "profiles_email_check"

-- ✅ ACCEPTED: NULL (no email provided)
INSERT INTO profiles (..., email) VALUES (..., NULL);
```

#### 3. Time Travel Prevention
```sql
-- ❌ REJECTED: updated_at before created_at
INSERT INTO profiles (full_name, linkedin_username, created_at, updated_at)
VALUES ('Test', 'test', '2025-01-01', '2024-01-01');
-- ERROR: new row violates check constraint "profiles_updated_at_check"
```

### Benefits
1. **Fail Fast**: Bad data caught at INSERT, not during query
2. **No Silent Corruption**: Database enforces data quality automatically
3. **Debugging Clarity**: Constraint name reveals exact violation
4. **Documentation**: Schema *is* the specification

---

## Migration Strategy

### Migration Files

| File | Purpose | Objects Created |
|------|---------|-----------------|
| `001_extensions.sql` | Enable pgvector, pg_trgm, uuid-ossp | 3 extensions |
| `002_staging_table.sql` | Create staging_profiles_raw | 1 table, 2 indexes |
| `003_core_schema.sql` | Create core tables with constraints | 5 tables, 28 constraints |
| `004_indexes.sql` | Performance indexes + statistics | 15+ indexes |

### Execution Order
1. Extensions (dependency for VECTOR type)
2. Staging table (independent)
3. Core schema (foreign keys require order)
4. Indexes (built AFTER data load for performance)

### Rollback Strategy
```bash
# Full reset with confirmation
poetry run reset-db

# Force reset (CI/CD)
poetry run reset-db --force
```

**Negative Space Validation**: `reset_db.py` checks for missing env vars, empty migration files, and SQL errors before proceeding.

---

## Verification Results

### Test Case: Constraint Enforcement

```sql
-- Test 1: Invalid years_experience
postgres=# INSERT INTO profiles (full_name, linkedin_username, years_experience)
           VALUES ('Test User', 'test_user', 150);
ERROR:  new row for relation "profiles" violates check constraint "profiles_years_experience_check"
DETAIL:  Failing row contains (test_user, 150, ...).
✅ PASS

-- Test 2: Valid insert
postgres=# INSERT INTO profiles (full_name, linkedin_username, years_experience)
           VALUES ('Test User', 'test_user_2', 5);
INSERT 0 1
✅ PASS

-- Test 3: Empty full_name
postgres=# INSERT INTO profiles (full_name, linkedin_username)
           VALUES ('   ', 'test_user_3');
ERROR:  new row for relation "profiles" violates check constraint "profiles_full_name_check"
✅ PASS
```

### Schema Statistics

```sql
-- Tables created
postgres=# \dt
                        List of relations
 Schema |         Name          | Type  |  Owner
--------+-----------------------+-------+----------
 public | companies             | table | postgres
 public | profile_certifications| table | postgres
 public | profile_education     | table | postgres
 public | profile_experiences   | table | postgres
 public | profiles              | table | postgres
 public | staging_profiles_raw  | table | postgres
(6 rows)
✅ 6 tables created

-- Extensions enabled
postgres=# \dx
                                      List of installed extensions
    Name     | Version |   Schema   |                        Description
-------------+---------+------------+-----------------------------------------------------------
 pg_trgm     | 1.6     | public     | text similarity measurement and index searching
 uuid-ossp   | 1.1     | public     | generate universally unique identifiers (UUIDs)
 vector      | 0.8.1   | public     | vector data type and ivfflat and hnsw access methods
✅ All extensions active
```

---

## Performance Considerations

### Estimated Storage (51M rows)

| Table | Est. Size | Notes |
|-------|-----------|-------|
| profiles | ~200GB | ~4KB/row (with embedding) |
| staging_profiles_raw | ~50GB | Temporary, purged after load |
| companies | ~500MB | ~10K unique companies |
| profile_experiences | ~30GB | ~150M rows (3 jobs/person avg) |
| profile_education | ~10GB | ~70M rows (1.4 degrees/person avg) |
| **Total** | **~290GB** | Plus indexes (~40% overhead) |

### Write Performance
- **Staging Import**: ~50,000 rows/sec (COPY with batching)
- **Core Transform**: ~10,000 rows/sec (constraint validation overhead)
- **Index Build**: ~2 hours for HNSW on 51M vectors (parallelized)

### Query Performance (See INDEX_REPORT.md)
- Vector search: <100ms (HNSW with ef_search=64)
- Hybrid search: <200ms (vector + FTS + filters)
- Skills filter: <50ms (GIN index)

---

## Addendum: Migrations 005–009

Added after this report was written (see `migrations/` for full SQL):

| Migration | What it adds |
|-----------|--------------|
| `005_data_completeness.sql` | `data_completeness_pct` (0–100) column + partial index — powers "completeness" filtering/ranking |
| `006_optimize_filter_indexes.sql` | Tuned B-tree/partial indexes for the most common filter combinations |
| `007_add_search_vector.sql` | Persisted `search_vector` tsvector column + GIN index (replaces on-the-fly `to_tsvector` in queries) |
| `008_users_and_api_keys.sql` | Auth schema: `users`, `api_keys` (SHA-256-hashed keys, scopes, tiers), `refresh_tokens`, `audit_log` |
| `009_performance_optimizations_10m.sql` | 10M-scale prep, including a `profiles_partitioned` LIST-partition-by-state experiment (top-10 states + default partition) |

Current loaded state: **497,552 profiles**, 0 embeddings generated (embedding column
exists; hybrid search falls back to full-text until embeddings are populated).

---

**Report Generated**: 2025-10-07 (addendum 2026-07-14)
**Database Version**: PostgreSQL 17.0
**pgvector Version**: 0.8.1
**Schema Version**: 1.0.0 + migrations 005–009
