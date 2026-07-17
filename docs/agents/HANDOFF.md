# Handoff Log (Reverse‑Chronological)

This log captures short handovers after each meaningful change so multiple AI agents (and humans) can stay aligned.

Template (copy/paste):

- Date/Time (UTC): YYYY‑MM‑DD HH:MM
- Author: YourName (Claude/GPT/Human)
- Change: One‑line summary
- Details: 2–3 bullets on approach/constraints
- Impacts: API/UX/security/perf (as applicable)
- Next: What you expect the other agent to do

- Date/Time (UTC): 2026-07-17 02:20
- Author: Claude (filters redesign)
- Change: Complete redesign of the `/` filters panel — compact two-column grid replacing the old full-width vertical stack
- Details:
  - New layout in `home.module.css` + `app/page.js`: header row (Filters + active-count badge, Clear all, × close), grid sections Role & company / Experience & skills (min–max on one row) / US states / Industries / Has contact info; 1-column on ≤900px
  - States/industries now use a `MultiSelectFilter` component: search box, removable selected chips (hover = red remove affordance), compact 148px option list with custom check squares — replaces the old 220px global-class checkbox containers (old globals.css classes untouched, page no longer uses them)
  - Contact filters are now toggle pills (aria-pressed, dark chip when active) with short labels (LinkedIn/Email/…) instead of the 6-checkbox grid; identical search params emitted — `/results` contract unchanged
- Impacts: UX only. Verified in both themes via headless-Chrome screenshots (panel opened, options toggled, chips/pills render)
- Next: Consider persisting open/closed filter panel state; possible follow-up to reuse MultiSelectFilter on `/results` for filter editing

- Date/Time (UTC): 2026-07-17 01:40
- Author: Claude (rays background)
- Change: Replaced the `/` page background (animated squares) with a WebGL SideRays light-ray effect, theme-aware in both modes
- Details:
  - New `components/SideRays.js` + `SideRays.module.css` — react-bits SideRays ported to plain JS (new dep: `ogl@1.0.11`); mounted full-viewport behind content via `.raysBackground` (fixed, z-index -1, pointer-events none) in `home.module.css`
  - Ray colors/opacity are theme tokens (`--rays-color-1/2`, `--rays-opacity` in globals.css): dark = #eab308/#96c8ff at 1.0 (user-provided), light = deeper #ca8a04/#3b82f6 at 0.55 so additive rays read on white; page re-reads tokens on the `themechange` event, and SideRays updates its uniforms live on prop change
  - Props per user spec: speed 2.5, intensity 2, spread 2, origin top-right, saturation 1.5, blend 0.75, falloff 1.6; `/results` still uses SquaresBackground (only `/` swapped)
- Impacts: UX only; verified in both themes via headless-Chrome screenshots (canvas renders, no console errors). Frontend gains a WebGL dependency; rays pause offscreen via IntersectionObserver
- Next: If the rays look right, consider swapping `/results` (and login/dashboard?) to SideRays for consistency, then retire SquaresBackground

- Date/Time (UTC): 2026-07-17 00:50
- Author: Claude (main page redesign)
- Change: Redesigned `/` as a Perplexity-style app shell — collapsible search-history sidebar + centered hero with a glowing search box (branch `feat/main-page-filter-redesign`)
- Details:
  - New layout in `app/page.js` + `app/home.module.css`: sidebar (brand, New Search, filterable "Recent" history list, nav/GitHubStars/ThemeToggle at bottom; hideable on desktop via panel button — persisted in localStorage `sidebarCollapsed`, floating reopen button — and off-canvas slide-over on ≤900px) and main pane (classic hero kept per user preference: PROSPECTIQ badge + "Search 497K+ {rotating}" + GTM tagline, reusing globals `.hero-title`; rounded search box with toolbar — Filters toggle w/ active-count badge, circular glow submit — suggestion chips/cards, hide-suggestions toggle, stat line); Header/Footer no longer used on `/` but untouched for other pages; SquaresBackground kept
  - Search history is localStorage-backed via new `lib/searchHistory.js` (capped at 50, dedupes identical params, `describeParams()` builds labels) — module is the single access point so the planned backend/DB persistence swaps in one place; clicking an entry re-runs it through the same `runSearch()` path as the form (sessionStorage → `/results`, unchanged contract)
  - All existing filters preserved verbatim (states/industries multi-select, job title, company, experience range, skills, contact checkboxes) in a panel toggled from the search-box toolbar, plus a new "Clear all filters"; suggestion cards run preset searches, chips prefill the keyword
- Impacts: UX only — no API changes; `/results` contract (sessionStorage `searchParams`) unchanged. `bun run build` passes; new-markup smoke-tested via curl on :5500. All colors via existing globals.css tokens (both themes)
- Next: Visual pass in both themes (incl. mobile sidebar), then design the history persistence API (per-user, JWT-scoped) to replace localStorage

---

- Date/Time (UTC): 2026-07-16 23:32
- Author: Codex
- Change: Migrated frontend package management from npm to Bun
- Details:
  - Added `frontend/bun.lock` via `bun install` and pinned `packageManager` to `bun@1.3.9`
  - Updated active setup docs and `scripts/serve_frontend_bg.sh` to use `bun install` / `bun run`
  - Removed npm lockfile tracking in favor of Bun's lockfile
- Impacts: Frontend dependencies and scripts should now be run with Bun; Next.js remains pinned to port :5500
- Next: Use `bun run build` for frontend build verification before release

---

- Date/Time (UTC): 2026-07-16 16:40
- Author: Claude (Next.js migration)
- Change: Migrated the entire frontend from static HTML/CSS/vanilla JS to Next.js 16 (App Router, plain JS, no Tailwind) on branch `feat/nextjs-migration` (10 commits, branched off `feat/light-mode`)
- Details:
  - All 6 pages ported as client components: `/` (search), `/results`, `/login`, `/dashboard`, `/api-docs`, `/test-api-key`; legacy `*.html` URLs 307-redirect via `next.config.mjs`; shared chrome in `components/` (Header, Footer, ThemeToggle, GitHubStars, SquaresBackground) and logic in `lib/` (config, auth, theme, squares-background)
  - `styles.css` → `app/globals.css` verbatim (all dual-theme tokens intact); theme.js's pre-paint logic now an inline bootstrap in `app/layout.js` + `lib/theme.js` API; page `<style>` blocks → CSS Modules; `npm run dev`/`start` pinned to :5500 so existing CORS defaults keep working (`scripts/serve_frontend_bg.sh` updated, requires `npm install` in frontend/)
  - Dead code dropped, not ported: RotatingText.js, ShapeBlur.js, three.js CDN tag, search.js `loadStats()`, results.js `convertToCSV()`; behavior preserved otherwise (sessionStorage search handoff, hybrid-weight query params, one-time API key display, cURL generator)
  - `.gitignore`: Node section added with negations (`!frontend/lib/`, `!package-lock.json`, `!jsconfig.json`) because the Python-era `lib/` and `*.json` patterns would silently swallow app source
- Impacts: UX/tooling only — no API changes. `npm run build` passes (all routes prerender); every route + redirect smoke-tested via curl on :5500. Frontend now needs Node/npm (was zero-build)
- Next: Visual pass in a browser (both themes), then prepare-pr for `feat/nextjs-migration`; consider deleting stale `.tmp/frontend_http.pid`

---

- Date/Time (UTC): 2026-07-16 15:10
- Author: Claude (light mode implementation)
- Change: Added a light theme with WCAG-AA contrast and a sun/moon toggle to all 6 frontend pages (branch `feat/light-mode`, 8 commits)
- Details:
  - `styles.css`: ~28 new tokens on `:root` (dark values = old literals, zero visual change) + a `[data-theme="light"]` override block; all hardcoded colors in styles.css/page `<style>` blocks/inline styles/JS-generated markup migrated to tokens; new shared components `.theme-toggle`, `.nav-link`, `.link-accent`, `.warning-box`, `.btn-copied`
  - New `frontend/theme.js` loads synchronously in `<head>` before styles.css (no FOUC): localStorage choice wins, else OS `prefers-color-scheme` (tracked live until user toggles); exposes `window.themeUtils`, dispatches `themechange`; `squares-bg.js` re-reads `--canvas-*` tokens on that event (also fixed its vignette inner-stop mismatch)
  - Light palette AA-verified (ratios documented in `docs/guides/THEME_GUIDELINES.md`): success/error/info/link accents darkened to 700-shades; buttons stay dark chips with new `--text-on-primary` (also fixed api-docs back-to-top/generate-button and count spans that would have been invisible); `test-api-key.html` now links styles.css instead of duplicating drifted hex
- Impacts: UX only — no API changes. Dark mode remains the default and is pixel-identical except intentional fixes noted above
- Next: Visual pass in both themes on all 6 pages (serve frontend on :5500), then prepare-pr for `feat/light-mode`

---

- Date/Time (UTC): 2026-07-14 (docs reorganization)
- Author: Claude (docs cleanup)
- Change: Reorganized all documentation into docs/{architecture,database,deployment,guides,agents,archive}; updated or removed outdated docs
- Details:
  - Moved root-level guides into docs/ (DEPLOYMENT_*, SCALING_*, QUICK_SCALE_REFERENCE, QUICK_START, HYBRID_SETUP, REBUILD_SUMMARY, README_local_dev) — completes the "move root .md guides under docs/" item from 2026-07-07
  - Rewrote docs/architecture/ARCHITECTURE.md to current state (three FastAPI apps, migrations 001–009, two auth systems, 0 embeddings/FTS fallback, S3/Athena state-partitioned cold tier); rewrote docs/README.md as the index; rewrote guides/SECURITY.md (removed one-time incident content)
  - Added status headers: NEXT_STEPS_ARCHITECTURE (Step 1 done, partitioned by state not country/industry), INGESTION_ARCHITECTURE (Tier 3 superseded by tiered warehouse), SCHEMA_REPORT (005–009 addendum), INDEX_REPORT
  - Archived (docs/archive/): PROJECT_PHASES, API_DESIGN_PROPOSAL (never implemented), CODEX_HANDOFF_2025-10-22. Deleted: ARCHITECTURE_VISUAL (abandoned Vue proposal), PHASE_STATUS, CRITICAL_ISSUES_AND_DEPLOYMENT_PLAN (fixed in 70bfdb0), MIGRATION_GUIDE, SCALING_PLAN (all recoverable from git)
  - Fixed stale "Side Projects/WebApplication" paths in agent.md, docs, and scripts; updated all cross-references (agent.md, README.md, CLAUDE.md, scripts)
- Impacts: Docs only — no code/API changes. All moves via git mv (history preserved); moves are staged, not committed
- Next: Commit as docs: batch; new docs go in the matching docs/ subfolder per docs/README.md conventions

---

- Date/Time (UTC): 2026-07-07 15:50
- Author: Claude (Athena cold-tier reshape)
- Change: Partitioned the full 51.35M-row S3 parquet into a state-partitioned Athena/Parquet warehouse (cold tier foundation)
- Details:
  - Source `s3://sungchunn-linkedin-db/USA_filtered.parquet` (15.2GB, 51,352,619 rows) is 99.9% US; profiling showed `Region`(state) is the clean partition key (2.3% null, even spread) vs `Company Industry` (49% null) — chose partition-by-state, not the doc's country/industry
  - Reshape run 100% in AWS via Athena CTAS (server-side copy → `raw/` prefix; external table `insight.profiles_raw` uses REAL parquet names in backticks + name mapping, NOT position mapping which mis-aligned; DML uses double-quoted identifiers). Output: `s3://sungchunn-linkedin-db/curated/usa_profiles/state=<state>/` = 52 partitions (50 states+DC+`other`); row count exact, cost ~$0.08, ~1min
  - Cleaning in CTAS: 56 cols → snake_case (dropped dot-named `Last Updated.1`), `years_experience`→int (out-of-range→null), `Region`→US-state whitelist else `other`. Data is dirty (CSV quote-bleed garbage in country/region)
  - Helper + SQL in session scratchpad (`athena.sh`, `create_raw_v2.sql`, `ctas.sql`); design context in `docs/NEXT_STEPS_ARCHITECTURE.md`
- Impacts: New cold-tier dataset on S3; no app/API wiring yet. IAM user `insight-s3-reader` has inline policy `insight-athena-reshape` (Athena+Glue+S3 rw on the bucket)
- Next: (1) USER must add `glue:GetPartition`+`glue:BatchGetPartition` to the inline policy so partition-pruned `WHERE state=` queries work (only plural `GetPartitions` granted). (2) Optional: delete redundant root `USA_filtered.parquet`; compact small-state partitions. (3) Then: precompute aggregates/dropdowns, wire DuckDB/Athena cold path into query router

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


---

- Date/Time (UTC): 2026-07-17
- Author: Claude Code
- Change: Renamed default branch `clean-main` → `main` (local + GitHub)
- Details:
  - Local branch renamed and pushed; upstream tracking set to `origin/main`
  - GitHub default branch switched to `main` via `gh repo edit`; remote `clean-main` deleted
  - `origin/HEAD` updated; stale tracking refs pruned
- Impacts: All future PRs target `main`; any local clones should run `git fetch --prune && git branch -m clean-main main && git branch -u origin/main main`
- Next: Optionally delete stale branches (`feat/nextjs-migration` local, `codex/clean-main-into-main` remote)
