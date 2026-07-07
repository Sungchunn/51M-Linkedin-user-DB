---
name: prepare-pr
description: Prepare the current feature branch for a pull request against main - sync with main (rebase before first push, merge after), generate a structured PR description from the actual branch diff, and hand the push/PR-create commands to the user. Use when the user asks to prepare a PR, open a PR, finish a branch, or run the PR workflow. Never pushes or opens the PR itself.
---

# Prepare PR

Prepare the current branch for a pull request against `main`. Follow the Git rules in `agent.md` (project root) at all times: **never force push, never add AI attribution, conventional commit formats.**

**Hard boundary: this skill NEVER runs `git push` or `gh pr create`. The human does the publishing step.**

## Step 1 — Preflight

1. `git rev-parse --abbrev-ref HEAD` — if the branch is `main`, **stop**: this workflow is only for feature branches.
2. `git status --porcelain` — if the working tree is dirty, stop and ask the user whether to commit (per Commit Strategy in `agent.md`) or stash before proceeding.
3. `git fetch origin main` to get the latest main.

## Step 2 — Sync the branch with main

Check whether the branch has ever been pushed: `git rev-parse --abbrev-ref @{upstream}` (fails if no upstream) or `git ls-remote --heads origin <branch>`.

- **Never pushed (no remote branch):** `git rebase origin/main`. This is the preferred, history-clean path.
- **Already pushed:** do NOT rebase — updating the remote would require a force push, which is forbidden. Use `git merge origin/main` instead and mention the merge in the PR description.

If a rebase hits conflicts you cannot resolve with high confidence from the surrounding code, run `git rebase --abort`, report the conflicting files to the user, and stop. Never resolve conflicts by guessing.

After a successful rebase/merge, re-run the test suite or at minimum verify the app still imports/starts if the sync pulled in meaningful changes.

## Step 3 — Analyze the branch diff

Build a real understanding of the change — the description must be written from the diff, not from memory:

```bash
git log --oneline origin/main..HEAD          # commits on this branch
git diff --stat origin/main...HEAD           # files + churn overview
git diff origin/main...HEAD                  # full diff; read large diffs file-by-file
```

Identify the **structural changes**: new/moved modules, schema or migration changes, API contract changes (endpoints, request/response shapes), new dependencies or services, config/infra changes, and behavior changes a reviewer must know about. Distinguish these from mechanical noise (renames, formatting).

## Step 4 — Write the PR description

Write the description to `.tmp/pr-description.md` (gitignored). Format:

```markdown
## Summary

2–4 sentences of plain English: what this branch does and why. No jargon,
no file paths — write for a reviewer who has not seen the code yet.

## Structural Changes

Grouped by area (Backend / Frontend / Database / Infra / Docs — omit empty
groups). Each bullet states the change in plain English and why it matters,
not just which file was touched:

- **Backend:** Search now falls back to keyword-only mode when no embeddings
  exist, so the API works before the embedding pipeline has run.

## Visuals

Include ONLY when they genuinely clarify — otherwise omit the section:
- Mermaid diagram (GitHub renders it) when the change alters architecture,
  request flow, or data flow.
- Table for endpoint changes, schema changes, or before/after comparisons.
- ASCII tree for new directory structures.

## Commits

Output of `git log --oneline origin/main..HEAD`.

## Verification

What was actually run (tests, manual checks) and what was NOT verified.
Be honest — never claim untested behavior works.
```

Rules:
- Title in conventional-commit format, e.g. `feat(api): environment-aware CORS configuration`.
- No AI attribution anywhere in the title or body (see `agent.md` Hard Rules).
- If the branch was synced by merge instead of rebase (Step 2), say so in the Summary.

## Step 5 — Hand off to the user (do not push)

Print the full PR description in the conversation for review, then give the user the exact commands to run themselves:

```bash
cd "<repo-root>" && \
git push -u origin <branch> && \
gh pr create --base main --head <branch> \
  --title "<conventional-commit title>" \
  --body-file .tmp/pr-description.md
```

Then stop. Do not run these commands, do not offer to run them "for convenience", and do not open the PR through any other means.
