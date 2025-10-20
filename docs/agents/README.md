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

