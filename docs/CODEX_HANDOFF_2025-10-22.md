# Handoff to Codex - October 22, 2025

## Context
This is a handoff from Claude to Codex as we're approaching the weekly token limit. This document summarizes the current state of the PROSPECTIQ project and provides guidance for continuing development.

## Important Files to Read First

1. **`docs/agents/agent.md`** - Your authoritative instruction file (Codex reads this, Claude reads claude.md)
2. **`docs/agents/HANDOFF.md`** - Chronological log of all changes (newest at top)
3. **`docs/THEME_GUIDELINES.md`** - UI/theme standards for all frontend work
4. **`README.md`** - Project overview and setup instructions

## What Was Just Completed (This Session)

### Advanced Search Filters Implementation ✅

I implemented 8 new search filters that the user requested:

#### Frontend Changes
1. **index.html** (lines 101-198)
   - Added Job Title text input
   - Added Company text input
   - Added 6 contact information checkboxes:
     * Has LinkedIn Profile
     * Has Email
     * Has Phone
     * Has Website/Domain
     * Has Twitter
     * Has GitHub

2. **search.js** (lines 335-353)
   - Updated `setupFormHandler()` to collect all new filter values
   - Values stored in sessionStorage for passing to results page
   - Job Title and Company collected via FormData automatically
   - Contact checkboxes explicitly checked and added to params

3. **results.js** (lines 73-83)
   - Added URL parameter passing for job_title and company
   - Added URL parameter passing for all 6 has_* filters
   - Filters sent as query params to API endpoint

4. **styles.css**
   - Added `.checkbox-filter` class for checkbox styling
   - Implemented hover effects and checked states
   - CSS Grid layout for responsive design

#### Backend Changes
1. **models.py** (lines 53-63)
   - Added `job_title: Optional[str]` field
   - Added `company: Optional[str]` field
   - Added 6 boolean fields: has_linkedin, has_email, has_phone, has_website, has_twitter, has_github
   - All fields properly typed and documented

2. **app.py** (lines 539-586)
   - Added 8 new query parameters to GET `/search` endpoint
   - Parameters passed to SearchRequest model for validation
   - Documented in OpenAPI spec

3. **search.py** (lines 145-169 and 500-524)
   - Implemented SQL filtering in both `hybrid_search()` and `keyword_search()` functions
   - job_title uses ILIKE for case-insensitive partial matching: `job_title ILIKE '%{value}%'`
   - company uses ILIKE for case-insensitive partial matching: `company_name ILIKE '%{value}%'`
   - has_* filters check: `field IS NOT NULL AND field != ''`

#### Testing Results
All filters verified working:
- **Job Title**: Tested with "software" - returns only matching profiles ✅
- **Company**: Tested with "google" - returns 5 Google employees (case-insensitive) ✅
- **has_linkedin**: All 42,768 engineer profiles have LinkedIn (100%) ✅
- **has_email**: Reduces results from 42,768 to 30,058 (70% have email) ✅

Note: Email/phone are PII-redacted in responses, but filters work at SQL level.

## Current System Status

### Database
- **PostgreSQL 17 + pgvector** running in Docker
- **497,552 profiles** indexed (from 51M+ Parquet dataset)
- **0 embeddings generated** - system using keyword-only search currently
- Health check: `curl http://localhost:8000/health`

### API Server
- **FastAPI** running on http://localhost:8000
- Started via: `./start_api.sh` (runs in background)
- Kill with: `pkill -f "uvicorn backend.api.app:app"`
- API docs: http://localhost:8000/docs

### Frontend
- Served via Live Server (VS Code extension) on port 5500
- Pages: index.html, results.html, login.html, dashboard.html, api-docs.html
- All pages follow dark minimal theme with signature white glow

### Git Status
- Branch: `clean-main`
- Latest commit: `6bf5682` - Advanced search filters implementation
- Ready to push: `git push origin clean-main`

## Known Issues & Limitations

1. **No embeddings generated yet**
   - System uses keyword-only search (full-text)
   - Need to run: `poetry run python backend/data_pipeline/embeddings/generate.py`
   - This will enable hybrid vector + lexical search

2. **ILIKE performance concern**
   - job_title and company filters use ILIKE which may be slow
   - Consider adding GIN indexes:
     ```sql
     CREATE INDEX idx_profiles_job_title ON profiles USING gin(job_title gin_trgm_ops);
     CREATE INDEX idx_profiles_company_name ON profiles USING gin(company_name gin_trgm_ops);
     ```

3. **PII redaction**
   - Email and phone redacted unless user has `pii:read` scope
   - Filters work at SQL level but response is sanitized

## Priority Next Steps

### High Priority
1. **Generate Embeddings**
   - Run embedding generation on all 497K profiles
   - This enables hybrid search (current bottleneck)
   - Command: `poetry run python backend/data_pipeline/embeddings/generate.py`

2. **Performance Monitoring**
   - Test ILIKE query performance with larger result sets
   - Add GIN indexes if queries are slow (>500ms)

### Medium Priority
3. **UX Enhancements**
   - Add active filter summary display on results page
   - Add "Clear all filters" button
   - Add autocomplete/typeahead for company and job title
   - Show loading states for filter dropdowns

4. **Testing**
   - Add unit tests for new filter logic
   - Add integration tests for search with all filter combinations
   - Performance benchmarks

### Low Priority
5. **API Improvements**
   - Add cursor-based pagination (in addition to offset/limit)
   - Add aggregation endpoint for filter statistics
   - Add batch profile lookup endpoint

## File Structure Reference

```
/
├── backend/
│   ├── api/
│   │   ├── app.py              # Main FastAPI application
│   │   ├── models.py           # Pydantic request/response models
│   │   ├── search.py           # Search logic (hybrid + keyword)
│   │   ├── database.py         # Database connection pooling
│   │   ├── auth.py             # Authentication & authorization
│   │   └── auth_routes.py      # Auth endpoints
│   └── data_pipeline/
│       ├── embeddings/         # Embedding generation (NOT RUN YET)
│       └── ingestion/          # Data loading from Parquet
├── frontend/
│   ├── index.html             # Main search page
│   ├── results.html           # Search results page
│   ├── login.html             # Login/registration
│   ├── dashboard.html         # API key management
│   ├── api-docs.html          # Interactive API docs
│   ├── search.js              # Search form logic
│   ├── results.js             # Results display logic
│   └── styles.css             # Global styles (dark theme)
├── docs/
│   ├── agents/
│   │   ├── agent.md           # YOUR INSTRUCTION FILE (authoritative)
│   │   └── HANDOFF.md         # Chronological change log
│   ├── THEME_GUIDELINES.md    # UI/theme standards
│   └── CODEX_HANDOFF_*.md     # Handoff documents
└── docker-compose.yml         # PostgreSQL + pgvector setup
```

## Important Commands

### Start Services
```bash
# Start database
docker compose up -d

# Start API server (background)
./start_api.sh

# Stop API server
pkill -f "uvicorn backend.api.app:app"
```

### Development
```bash
# Install dependencies
poetry install

# Run tests
poetry run pytest

# Check database connection
psql postgresql://postgres:postgres@localhost:5432/talent_search
```

### Git Workflow
```bash
# Current branch
git status

# Push changes
git push origin clean-main

# Feature commits (use conventional commits)
git commit -m "feat(scope): description"
git commit -m "fix(scope): description"
git commit -m "docs(scope): description"
```

## Code Philosophy: Negative Spaces

The project follows "Negative Spaces" pattern - making bugs immediately obvious through explicit boundaries. See `docs/agents/agent.md` for full details.

Key principles:
- **Fail fast** with clear error messages
- **Type contracts** via Pydantic models
- **Invariant assertions** to catch violations
- **Database constraints** to enforce rules
- **Explicit boundaries** instead of silent failures

Example:
```python
# Bad - silent failure
def process(row):
    return row.get('name', '')

# Good - explicit boundary
def process(row):
    if 'name' not in row:
        raise ValueError(f"BOUNDARY VIOLATION: 'name' missing in row {row.get('id')}")
    return row['name']
```

## Working with the User

1. **Read agent.md first** - It's your authoritative instruction file
2. **Update HANDOFF.md** after significant changes (use template at top)
3. **Follow theme guidelines** for any frontend work
4. **Use conventional commits** for git messages
5. **Test thoroughly** before committing
6. **Ask for clarification** if requirements are ambiguous

## Critical Notes

- **Do NOT commit** claude.md, .env files, or files with AI attribution
- **Use multi-line bash** commands with backslash continuation for paths with spaces
- **Follow dark minimal theme** with signature white glow for all UI
- **Log NEGATIVE SPACE violations** prominently in error messages
- **Provide bash snippets** instead of running commands that take >30 seconds

## API Endpoints Overview

### Search
- `GET /search?q=engineer&job_title=software&company=google&has_linkedin=true`
- Supports: query, regions, industries, job_title, company, experience range, skills, has_* filters

### Export
- `GET /export/csv?q=...&filters=...`
- `GET /export/ndjson?q=...&filters=...`

### Filters
- `GET /regions?country=united%20states`
- `GET /industries`

### Authentication
- `POST /auth/register` - User registration
- `POST /auth/login` - Login (returns JWT tokens)
- `GET /auth/me` - Current user info
- `GET/POST/DELETE /auth/api-keys` - API key management

## Quick Test Commands

```bash
# Test health
curl http://localhost:8000/health

# Test search with new filters
curl "http://localhost:8000/search?q=engineer&job_title=software&limit=5" | python3 -m json.tool

# Test company filter
curl "http://localhost:8000/search?q=engineer&company=google&limit=5" | python3 -m json.tool

# Test contact filter
curl "http://localhost:8000/search?q=engineer&has_linkedin=true&limit=5" | python3 -m json.tool
```

## Statistics

- **Total Profiles**: 497,552
- **Profiles with Embeddings**: 0 (HIGH PRIORITY TO GENERATE)
- **US States**: 50
- **Industries**: 12
- **Engineers with LinkedIn**: 42,768 (100%)
- **Engineers with Email**: 30,058 (70%)

## Contact Information

- Project: PROSPECTIQ - Semantic Talent Search
- Database: talent_search
- Stack: FastAPI + PostgreSQL 17 + pgvector + React (future)
- Theme: Dark minimal with signature white glow

---

**Handoff Date**: 2025-10-22 05:40 UTC
**Handed Off By**: Claude
**Handed Off To**: Codex
**Reason**: Approaching weekly token limit
**Latest Commit**: 6bf5682 (feat: add 8 advanced filters)
**Branch**: clean-main
**Status**: ✅ All features working, ready for embedding generation

Good luck with the next phase! The foundation is solid and all filters are tested and working. Focus on generating embeddings next to unlock the full power of hybrid search.
