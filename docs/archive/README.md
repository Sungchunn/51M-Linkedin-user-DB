# Archive

Superseded documents kept for historical context. **Nothing in this folder describes
the current system** — see [`docs/README.md`](../README.md) for the live index.

| Document | What it was | Superseded by |
|----------|-------------|---------------|
| [PROJECT_PHASES.md](./PROJECT_PHASES.md) | Original phase 0–6 build plan with per-phase test cases (the `test_phase*.py` suites are still named after it) | [agents/HANDOFF.md](../agents/HANDOFF.md) for progress; [architecture/NEXT_STEPS_ARCHITECTURE.md](../architecture/NEXT_STEPS_ARCHITECTURE.md) for the roadmap |
| [API_DESIGN_PROPOSAL.md](./API_DESIGN_PROPOSAL.md) | 2025-10 proposal for URL versioning (`/v1/`), generated client SDK, and strict contracts — never implemented | Current endpoints documented in [architecture/ARCHITECTURE.md](../architecture/ARCHITECTURE.md) |
| [CODEX_HANDOFF_2025-10-22.md](./CODEX_HANDOFF_2025-10-22.md) | Point-in-time Claude→Codex handoff snapshot (497K profiles, filter work) | [agents/HANDOFF.md](../agents/HANDOFF.md) (rolling log) |

Deleted outright in the 2026-07-14 docs reorganization (recoverable from git history):
`ARCHITECTURE_VISUAL.md` (abandoned Vue.js migration proposal), `PHASE_STATUS.md`
(stale 9,938-profile snapshot), `CRITICAL_ISSUES_AND_DEPLOYMENT_PLAN.md` (its blocking
issues were fixed in commit `70bfdb0`), `MIGRATION_GUIDE.md` (obsolete paths/ports;
hybrid track covered by `architecture/HYBRID_SETUP.md`), and `SCALING_PLAN.md`
(superseded by `deployment/SCALING_TO_51M_GUIDE.md` and the tiered-warehouse roadmap).
