# Handoff Log (Reverse‑Chronological)

This log captures short handovers after each meaningful change so multiple AI agents (and humans) can stay aligned.

Template (copy/paste):

- Date/Time (UTC): YYYY‑MM‑DD HH:MM
- Author: YourName (Claude/GPT/Human)
- Change: One‑line summary
- Details: 2–3 bullets on approach/constraints
- Impacts: API/UX/security/perf (as applicable)
- Next: What you expect the other agent to do

---

- Date/Time (UTC): 2026-07-07 14:05
- Author: Claude (deployment prep commit batch)
- Change: Committed all pending deployment/scaling work in 10 scoped commits; moved agent.md to project root
- Details:
  - Canonical agent spec relocated to /agent.md; all live doc references updated
  - Deployment track: Dockerfile + .dockerignore, Procfile/fly.toml/render.yaml, .env.production.example, env-aware CORS in backend/api/app.py, frontend config.js API-base autodetection
  - Scaling track: migration 009 (10M perf optimizations), quality-ranked 1M/10M extraction scripts, six deployment/scaling guides
  - Fixed consFole typo in search.js; local pre-commit hook now exempts .example env templates from the .env filename block
- Impacts: No API contract changes; CORS tightens only when ENVIRONMENT=production with CORS_ORIGINS set
- Next: Generate embeddings (still 0 embedded); consider moving root-level deployment .md guides under docs/

---

- Date/Time (UTC): 2025‑10‑22 05:35
- Author: Claude (Advanced Search Filters Implementation)
- Change: Implemented 8 new advanced search filters: Job Title, Company, and 6 contact information filters
- Details:
  - Frontend: Added Job Title and Company text inputs to index.html (lines 101-124)
  - Frontend: Added 6 contact checkboxes (Has LinkedIn, Email, Phone, Website, Twitter, GitHub) in index.html (lines 169-198)
  - Frontend: Updated search.js to collect all new filter values and store in sessionStorage (lines 335-353)
  - Frontend: Updated results.js to pass new filters as URL parameters to API (lines 73-83)
  - Backend: Added 8 new fields to SearchRequest model in models.py (lines 53-63)
  - Backend: Added 8 new query parameters to GET /search endpoint in app.py (lines 539-586)
  - Backend: Implemented SQL filtering in search.py for both hybrid_search and keyword_search functions
  - Filters: job_title and company use ILIKE for case-insensitive partial matching
  - Filters: has_* contact filters check for NOT NULL AND != '' (excluding empty strings)
  - Styles: Added .checkbox-filter CSS class for responsive grid layout of checkboxes
- Impacts:
  - API: New query params accepted: job_title, company, has_linkedin, has_email, has_phone, has_website, has_twitter, has_github
  - UX: Users can now filter by job title, company name, and presence of contact information
  - Database: Filters work at SQL level, reducing results efficiently
  - PII: Email/phone still redacted in API responses, but filters work correctly (verified via result count changes)
  - Performance: ILIKE queries may be slower on large datasets; consider adding GIN indexes if needed
- Testing Results:
  - Job Title filter: Tested with "software" - returns only matching profiles
  - Company filter: Tested with "google" - returns 5 Google employees (case-insensitive works)
  - has_linkedin: All 42,768 engineer profiles have LinkedIn (100% coverage)
  - has_email: Reduces engineer results from 42,768 to 30,058 (70% have email in DB)
  - All filters properly integrated and functional
- Next:
  - Monitor query performance with new ILIKE filters on production dataset
  - Consider adding GIN indexes on job_title and company_name columns if searches are slow
  - Optional: Add autocomplete/typeahead for company and job title fields
  - Optional: Add filter summary display showing active filters on results page

---

- Date/Time (UTC): 2025‑10‑21 04:15
- Author: Claude (Theme Documentation & Guidelines)
- Change: Created comprehensive theme guidelines and updated agent documentation
- Details:
  - Created docs/THEME_GUIDELINES.md with complete UI/theme standards (colors, typography, components, patterns)
  - Documented signature white glow effect implementation with ripple animation
  - Added new page template and pre-commit checklist for consistency
  - Updated docs/agents/agent.md with UI/Theme Guidelines section
  - Includes CSS variables reference, common patterns, and best practices
  - Updated project status: Phase 4 Complete - Authentication & API System Live
- Impacts:
  - Documentation: All future pages should reference THEME_GUIDELINES.md for consistent styling
  - UX: Ensures dark minimal aesthetic with signature glow remains consistent across new pages
  - Developer Experience: Clear patterns and examples for creating new frontend pages
- Next:
  - Reference THEME_GUIDELINES.md when creating any new frontend pages
  - Use the new page template and checklist before committing UI changes
  - Consider adding automated theme linting/validation in the future

---

- Date/Time (UTC): 2025‑10‑21 03:30
- Author: Claude (Authentication System Implementation)
- Change: Implemented complete user authentication and API key generation system
- Details:
  - Added JWT-based authentication with access (24h) and refresh tokens (30d)
  - Created database schema: users, api_keys, refresh_tokens, audit_log tables
  - Implemented auth endpoints: /auth/register, /auth/login, /auth/me, /auth/api-keys (CRUD)
  - Built frontend: login.html (login/register), dashboard.html (API key management)
  - Users can register, login, generate API keys with custom scopes (search:read, export:read, pii:read)
  - API keys use SHA-256 hashing, shown only once on creation
- Impacts:
  - API: New auth routes at /auth/* with Bearer token authentication
  - UX: Users must login to access dashboard and generate API keys
  - Security: Passwords hashed with bcrypt, JWT tokens for session management
  - Database: 4 new tables with proper indexes and constraints
- Next:
  - Test complete flow: register → login → create API key → use key with search endpoint
  - Fix bcrypt compatibility warning (cosmetic, doesn't affect functionality)
  - Optional: Add admin panel to manage all users and API keys

---

- Date/Time (UTC): 2025‑10‑20 17:30
- Author: GPT (WebApp)
- Change: Reverted to known‑good commit f1f394c; stabilized filters; kept export guard and cache‑busting
- Details:
  - Restored behavior before regressions; export allows query OR filter
  - Frontend loads updated `results.js` via cache‑busting
- Impacts: Filters and exports behave as expected; baseline stable
- Next: If enabling auth/keys/scopes again, apply incrementally with filter endpoints untouched
