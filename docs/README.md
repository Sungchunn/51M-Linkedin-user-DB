# PROSPECTIQ (INSIGHT) Documentation

All project documentation lives in this directory, organized by topic. The canonical
AI-agent spec is [`agent.md`](../agent.md) at the project root — read that first.

## Directory Map

```
docs/
├── architecture/   # System design — how the pieces fit together
├── database/       # Schema and index design reports
├── deployment/     # Deploying and scaling to production
├── guides/         # How-to guides and standards (setup, theme, security, philosophy)
├── agents/         # AI-agent collaboration protocol and handoff log
└── archive/        # Superseded plans and proposals, kept for history
```

## Architecture (`architecture/`)

| Document | What it covers |
|----------|----------------|
| [ARCHITECTURE.md](./architecture/ARCHITECTURE.md) | Current system architecture: the three FastAPI apps, request path, schema lineages, auth, data pipeline |
| [NEXT_STEPS_ARCHITECTURE.md](./architecture/NEXT_STEPS_ARCHITECTURE.md) | **Active roadmap** — tiered warehouse (hot Postgres / cold S3+Athena) and the NL search agent design |
| [INGESTION_ARCHITECTURE.md](./architecture/INGESTION_ARCHITECTURE.md) | Three-tier data-loading strategy (simple / optimized / cloud workers) |
| [HYBRID_SETUP.md](./architecture/HYBRID_SETUP.md) | Alternate hybrid track: Postgres hot tier + Redis + DuckDB-over-S3 (`backend/app.py`, `sql/`, Makefile) |
| [REBUILD_SUMMARY.md](./architecture/REBUILD_SUMMARY.md) | What the hybrid rebuild delivered, file by file |
| [README_local_dev.md](./architecture/README_local_dev.md) | Local dev setup for the hybrid track (MacBook Air M2) |

## Database (`database/`)

| Document | What it covers |
|----------|----------------|
| [SCHEMA_REPORT.md](./database/SCHEMA_REPORT.md) | Core schema design (migrations 001–004) plus addendum for 005–009 |
| [INDEX_REPORT.md](./database/INDEX_REPORT.md) | Index strategy: HNSW vector, GIN full-text/arrays, B-tree filters |

## Deployment & Scaling (`deployment/`)

| Document | What it covers |
|----------|----------------|
| [DEPLOYMENT_GUIDE.md](./deployment/DEPLOYMENT_GUIDE.md) | Deploying to Railway / Render / Fly.io |
| [DEPLOYMENT_READINESS_REPORT.md](./deployment/DEPLOYMENT_READINESS_REPORT.md) | Pre-production audit results |
| [DEPLOYMENT_CHANGES_SUMMARY.md](./deployment/DEPLOYMENT_CHANGES_SUMMARY.md) | Summary of the deployment-prep change batch (Nov 2025) |
| [SCALING_TO_51M_GUIDE.md](./deployment/SCALING_TO_51M_GUIDE.md) | Full 497K → 51M scaling strategy |
| [SCALING_SUMMARY.md](./deployment/SCALING_SUMMARY.md) | Scaling infrastructure overview |
| [QUICK_SCALE_REFERENCE.md](./deployment/QUICK_SCALE_REFERENCE.md) | TL;DR scaling commands and cost tiers |

## Guides & Standards (`guides/`)

| Document | What it covers |
|----------|----------------|
| [QUICK_START.md](./guides/QUICK_START.md) | 3-step start for the zero-storage DuckDB browse API |
| [THEME_GUIDELINES.md](./guides/THEME_GUIDELINES.md) | **Required for all frontend work** — dark minimal theme, CSS variables, white-glow buttons |
| [NEGATIVE_SPACES_GUIDE.md](./guides/NEGATIVE_SPACES_GUIDE.md) | The project's coding philosophy: explicit boundaries, fail-fast invariants |
| [SECURITY.md](./guides/SECURITY.md) | Credential handling, IAM policy, rotation, incident response |

## Agents (`agents/`)

| Document | What it covers |
|----------|----------------|
| [README.md](./agents/README.md) | How AI agents should use `agent.md` and the handoff protocol |
| [HANDOFF.md](./agents/HANDOFF.md) | Reverse-chronological log of meaningful changes — append after each one |

## Archive (`archive/`)

Superseded documents kept for historical context — do not treat as current:

- [PROJECT_PHASES.md](./archive/PROJECT_PHASES.md) — original phase 0–6 plan with test cases (tests in `backend/tests/` are still named after these phases)
- [API_DESIGN_PROPOSAL.md](./archive/API_DESIGN_PROPOSAL.md) — API versioning/SDK proposal (never implemented)
- [CODEX_HANDOFF_2025-10-22.md](./archive/CODEX_HANDOFF_2025-10-22.md) — point-in-time agent handoff snapshot

## Quick Navigation

**New to the project?** Read [../README.md](../README.md), then
[architecture/ARCHITECTURE.md](./architecture/ARCHITECTURE.md), then
[guides/NEGATIVE_SPACES_GUIDE.md](./guides/NEGATIVE_SPACES_GUIDE.md).

**Building a feature?** Check [architecture/ARCHITECTURE.md](./architecture/ARCHITECTURE.md)
for which app/track you're touching, [database/SCHEMA_REPORT.md](./database/SCHEMA_REPORT.md)
for the data model, and [guides/THEME_GUIDELINES.md](./guides/THEME_GUIDELINES.md) for any UI.

**Planning the next milestone?** [architecture/NEXT_STEPS_ARCHITECTURE.md](./architecture/NEXT_STEPS_ARCHITECTURE.md)
is the active roadmap; progress is logged in [agents/HANDOFF.md](./agents/HANDOFF.md).

**Deploying?** Start with [deployment/QUICK_SCALE_REFERENCE.md](./deployment/QUICK_SCALE_REFERENCE.md),
then [deployment/DEPLOYMENT_GUIDE.md](./deployment/DEPLOYMENT_GUIDE.md).

## Conventions

- New documentation goes in the matching subfolder here — never the repo root.
- Docs use Markdown, relative links, and a "Last Updated" date.
- When a doc becomes obsolete, move it to `archive/` (or delete it) and update this index.
- After each meaningful change, append an entry to [agents/HANDOFF.md](./agents/HANDOFF.md).

---

**Last Updated**: 2026-07-14
