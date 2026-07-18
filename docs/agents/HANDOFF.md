# Handoff Log (Reverse‑Chronological)

This log captures short handovers after each meaningful change so multiple AI agents (and humans) can stay aligned.

Template (copy/paste):

- Date/Time (UTC): YYYY‑MM‑DD HH:MM
- Author: YourName (Claude/GPT/Human)
- Change: One‑line summary
- Details: 2–3 bullets on approach/constraints
- Impacts: API/UX/security/perf (as applicable)
- Next: What you expect the other agent to do

- Date/Time (UTC): 2026-07-17 03:40
- Author: Claude (results table redesign)
- Change: Restyled the `/results` summary/table/pagination to the app-shell design language (both themes) via a new `results.module.css`
- Details:
  - Summary card: "9,354 results" heading + mono query-time pill (success tint <1s), quoted keyword, filter chips, pill Save + dark glow Export CSV buttons; table card: 16px radius, internal scroll (`.tableScroll`), sticky compact headers, capitalized name/title/company cells, muted summary/skills; pagination: pill Previous/Next, styled rows-select, mono page info; First/Last name merged into one Name column (display only — API fields unchanged)
  - Removed ~230 lines of legacy results globals from `globals.css` (`.results-*`, `.table-container`, bare `table/th/td` rules, old pagination/states) — all verified unused; the bare `td:nth-child(7) {text-align:center}` was leaking into the new table (centered Summary column) and `table {min-width:2700px}` leaked into api-docs tables
  - api-docs is auth-gated (redirects to login when unauthenticated) and styles its tables via its own module — unaffected
- Impacts: UX only. Verified via headless Chrome in both themes: live query renders, summary column left-aligned, experience centered, no page overflow, no console errors
- Next: A logged-in visual pass of /api-docs and /dashboard tables to confirm the globals cleanup left them untouched

- Date/Time (UTC): 2026-07-17 03:00
- Author: Claude (results page shell)
- Change: Extracted the new chrome into a shared `AppShell` component and applied it to `/results`
- Details:
  - New `components/AppShell.js` + `AppShell.module.css`: rays background, collapsible history sidebar, main pane — moved verbatim from the home page; pages pass `mainClassName` for their own main-pane layout (home passes `.homeMain` centering) and optional `onNewSearch`; history rerun from `/results` reloads in place via sessionStorage
  - `app/page.js`/`home.module.css` slimmed to content-only (hero, search box, filters, suggestions); `/results` now renders inside AppShell instead of Header/Footer/SquaresBackground (those components remain for login/dashboard)
  - Fixed a real overflow bug the swap exposed: `.results-container`'s `margin: 0 auto` disables flex-stretch inside the shell's main, so it sized to its 1400px max-width and overflowed the viewport by 220px — added `width: 100%` (globals.css)
- Impacts: UX only; `/results` data flow unchanged. Verified via headless Chrome: both pages screenshot correctly, live search renders 9,354 results, `scrollWidth === innerWidth` after the fix, no console errors
- Next: Port login/dashboard/api-docs to AppShell (or intentionally keep them standalone), then retire Header/Footer/SquaresBackground

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

---

- Date/Time (UTC): 2026-07-17
- Author: Claude Code
- Change: Applied user-designed redesign — search filter panel, results table, and contact detail slide-over
- Details:
  - Home filter panel: animated collapse (grid-rows 0fr→1fr), header with Clear all (filters only, keyword survives), states/industries as chip clouds (selected accent chips + "+ option" quick-add, capped at 8, search narrows), contact toggles moved to a footer bar with an "Apply filters" submit button; Filters toggle gets accent active state + rotating chevron
  - Results page: summary card replaced by a page header (count + query-time mono chip + Edit search/Save/Export CSV); active filters render as removable accent chips built from searchParams (removal persists to sessionStorage and re-runs from page 1; "location: United States" is fixed)
  - Results table: 14-column <table> replaced by a 6-column grid (Name & role with initials avatar, Company, Location, Exp, 2-line-clamped Summary, row actions LinkedIn/copy-contact); rows are keyboard-accessible buttons; pagination moved into the card footer
  - Contact detail slide-over: clicking a row opens a right drawer (min(560px, 92vw), scrim, Escape/scrim-click closes, body scroll locked) with identity band, LinkedIn/copy-email actions, Summary, Experience, Contact rows (linkedin/email/phone/website/twitter/github), Skills chips, and Details — fields dropped from the table remain reachable here
  - Theme: new token pair --accent-soft/--accent-line (both themes) for chip surfaces; SideRays kept on both pages with contrast raised slightly (intensity 2→2.4, light-mode --rays-opacity 0.55→0.62)
- Impacts: UX only — search request/response contracts unchanged; CSV export untouched; per-row PII columns (email/phone) moved from the table into the drawer
- Next: Verify drawer + chip-removal flows in the browser (Chrome extension was disconnected; verified via dev-server compile + API shape checks); consider restoring form state on "Edit search"

---

- Date/Time (UTC): 2026-07-17
- Author: Claude Code
- Change: Moved contact requirements out of the filter panel into a standalone popover selector
- Details:
  - New "Contact" button in the search toolbar (next to Filters) with its own count badge; opens a compact 220px popover with tickable rows for LinkedIn/Email/Phone/Website/Twitter/GitHub plus a Clear action
  - Popover closes on outside click or Escape; hint text "Only include profiles that have:" keeps the has_* filter semantics clear
  - Filter panel footer now holds only "Apply filters"; panel "Clear all" no longer touches contacts (popover has its own Clear; New Search still resets everything); contacts excluded from the Filters badge count
- Impacts: UX only — search params (has_*) unchanged; results-page "has: X" chips unaffected
- Next: Same as previous entry — browser-verify the interactive flows

---

- Date/Time (UTC): 2026-07-17
- Author: Claude Code
- Change: Backend service for per-user search history (backs the redesigned sidebar)
- Details:
  - Migration `010_search_history.sql`: `search_history` table (id, user_id FK→users ON DELETE CASCADE, label, params JSONB, params_signature, created_at/updated_at) with UNIQUE (user_id, params_signature) and a (user_id, updated_at DESC) index; applied to the local DB
  - New `/history` endpoints (JWT-authenticated via existing `get_current_user`): GET (newest-first list), POST (upsert — identical params by canonical-JSON SHA-256 signature bump the existing row instead of duplicating; history trimmed to 50 per user in the same transaction), DELETE /history/{id} (404 if not owned), DELETE /history (clear, idempotent)
  - Entry shape matches `frontend/lib/searchHistory.js` exactly: `{id, label, params, ts}` with ts as epoch ms — params are opaque to the API (stored verbatim, replayed by the client)
  - New modules `backend/api/history_manager.py` + `backend/api/history_routes.py`; models `SearchHistoryEntryCreate`/`SearchHistoryEntry` in models.py; router registered in `backend/api/app.py`
  - Tests: `backend/tests/test_search_history.py` (11 cases: auth required, add/list, dedupe-bump, ordering, remove, clear, user isolation, validation, 50-cap, cleanup) — all pass; includes a per-test pool-reset fixture because the global asyncpg pool binds to the first test's event loop (same pre-existing issue makes full-file `test_phase4.py` runs fail — not addressed here)
  - Verified live end-to-end with curl: register → login → POST/POST-bump/GET/DELETE, 403 unauthenticated
- Impacts:
  - API: new authenticated `/history` routes; no changes to existing endpoint contracts
  - Database: migration 010 must be applied in any environment before deploying this API version
- Next:
  - Wire `frontend/lib/searchHistory.js` to these endpoints for logged-in users (module is the designed single swap point); keep localStorage as the anonymous fallback
  - Decide semantics for the results-page "Save" button (currently a window.print() placeholder)

---

- Date/Time (UTC): 2026-07-18
- Author: Claude Code
- Change: Frontend search-history swap — sidebar now uses the /history API for logged-in users
- Details:
  - `lib/searchHistory.js` rewritten as the planned single swap point: all functions async; authenticated users (JWT in localStorage via `lib/auth.js`) read/write the `/history` endpoints, anonymous users keep localStorage; entry shape `{id,label,params,ts}` identical in both stores
  - Fail-soft by contract (never throws): API errors log a console.warn and degrade to empty list / no-op — deliberately NO cross-store fallback (would split history between stores)
  - Call sites updated: AppShell loads history async, delete/clear are optimistic UI updates, rerun awaits the bump before the full-page reload (which would abort an in-flight fetch); home `runSearch` awaits the save before navigating
  - Verified: `bun run build` clean; live curl flow (register → login → POST frontend-shaped entry → list) against the API
  - Context: PR #4 (`feat/main-page-filter-redesign`) was already merged to main via merge commit, so `feat/search-history-api` is the only branch left to land
- Impacts: Logged-in search history now syncs across devices/sessions; anonymous behavior unchanged; no API contract changes
- Next: PR `feat/search-history-api` → main; possible follow-up: migrate anonymous localStorage history into the account on first login

---

- Date/Time (UTC): 2026-07-18
- Author: Claude Code
- Change: Embedding pipeline verified and fixed — ready for the full 497K run (branch `fix/embedding-generation-pagination`)
- Details:
  - Found via 300-profile live test prep: `generate_all_embeddings` paginated with `OFFSET` over a `WHERE embedding IS NULL` set that shrinks as rows embed — a full run would have skipped ~half the profiles and reported success; also the CLI limit didn't clamp the fetch (limit 200 embedded 5000) and `ORDER BY created_at` without a tiebreaker made pagination nondeterministic on bulk-loaded ties
  - Fix: fetch always at offset = total_failed (failed rows stay NULL and sort before unprocessed ones), loop on processed count, clamp fetch to remaining limit, `ORDER BY created_at, id`
  - Live test: 300 profiles embedded (BATCH_SIZE_IO=100 → 3 iterations), verified embedded set == first 300 by (created_at,id) exactly (EXCEPT query: 0 missing/0 unexpected), 1536 dims; test embeddings then cleared so search keeps keyword fallback until the full run
  - Measured ~66 profiles/s steady state → full 497,552 ≈ 2–3.5h sequential, ~30M tokens ≈ $0.60; run is resumable (embedded rows drop out of the fetch)
  - Note: HNSW index from migration 004 does NOT exist in the local DB — build it AFTER the run (bulk update into an existing HNSW index would be much slower)
- Impacts: No behavior change until the run happens; search.py still keyword-only (0 embeddings)
- Next: user runs `poetry run generate-embeddings`, then creates the HNSW index (see migration 004 definition), then verify hybrid search activates

---

- Date/Time (UTC): 2026-07-18
- Author: Claude Code
- Change: Parallelized embedding generation (EMBED_CONCURRENCY, default 12)
- Details:
  - `generate_embeddings_batch` fans sub-batch OpenAI calls out to a ThreadPoolExecutor; all psycopg writes/commits stay on the calling thread (connection is not thread-safe); progress bar advances per completed sub-batch via callback
  - Live test: 2,000 profiles in ~17s (~115/s burst vs ~66/s sequential); exact-set verified via pre-run ID snapshot (all 2,000 expected rows embedded, 0 strays)
  - User had already started + interrupted a sequential run (5,200 embedded, kept — run is resumable); total now 7,200/497,552
- Impacts: Remaining ~490K projected 30–70 min instead of 2–3.5h; cost unchanged (~$0.60 total)
- Next: rerun `poetry run generate-embeddings` to completion, then build the HNSW index, then verify hybrid search

---

- Date/Time (UTC): 2026-07-18
- Author: Claude Code
- Change: Page size raised 50 → 200 (branch `feat/page-size-200`)
- Details:
  - `PUBLIC_MAX_LIMIT` default 50 → 200 (auth.py; env-overridable); fixed latent `SearchResponse.limit le=100` validator that would 500 on any page > 100 (now le=1000, matching the request model and trusted tier)
  - Frontend requests 200/page (home submit, history rerun, results default) and the rows-per-page select gains a 200 option
  - Verified live: browse returns exactly 200 rows; limit=900 clamps to 200; `bun run build` clean
  - Discovered while testing: with 497K embeddings now present but NO HNSW index yet, `hybrid_search` takes the vector path and every text query seq-scans to a 30s timeout → 500. Keyword/text search is DOWN until the index build completes (browse/filter-only queries unaffected)
- Impacts: Larger pages for all tiers' floors; text search outage until `scripts/run_embeddings.sh` (on `fix/embedding-generation-pagination`) finishes the index build
- Next: user completes Docker disk-limit raise + index build; then PR this branch
