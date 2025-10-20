# Agent Docs

- Purpose: Keep all AI agent instruction files organized and unambiguous.
- Canonical file: `docs/agents/agent.md` (commit this; it is the single source of truth).
- Local-only file: `docs/claude.md` (optional helper for local context; already in `.gitignore`).

## Usage With Any AI (Claude, OpenAI, etc.)

- Always load: `docs/agents/agent.md`.
- If both `docs/agents/agent.md` and `docs/claude.md` are present, treat `agent.md` as authoritative and ignore conflicts from `claude.md`.

Prompt snippet you can paste into any session:

```
Use docs/agents/agent.md as the authoritative agent spec.
If docs/claude.md is present, treat it as local-only context.
When there is any conflict, agent.md takes precedence.
```

## Contributing

- Update `agent.md` for any changes to agent behavior or workflow.
- Keep `claude.md` for local working notes only; do not rely on it for canonical rules.

## Handoff Protocol (Collaboration)

- After each meaningful commit or doc change, append a short entry to `docs/agents/HANDOFF.md`.
- Keep entries concise (5–8 lines) and include:
  - Context: what changed (feature/fix/docs)
  - Rationale: why this approach
  - Impacts: API/UX/limits/security
  - Next: what you expect the other agent to do next
- Use the template in `Handoff.md` and place newest entries at the top (reverse‑chronological).

Commit message hint:
- Add a trailer `Handoff: brief-summary-here` to surface the entry in git history.
