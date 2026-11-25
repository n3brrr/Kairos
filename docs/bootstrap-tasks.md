# Bootstrap tasks

Kairos does not exist yet, so its first tasks live here. They use the same format they will have in Kairos (type, status, criteria) so they can be migrated without rewriting. In stage 1 they are imported into Kairos and this file stays as history.

Statuses: `ready` · `in_progress` · `in_review` · `done`. IDs: `BOOT-nn`.

## BOOT-001 — Project context in the repo
- **Type:** docs · **Status:** `in_review` · **Branch:** `docs/BOOT-001-project-context`
- **Criteria:**
  - [x] `CLAUDE.md` with map, golden rules and git flow.
  - [x] `docs/` with status, roadmap, ideas, glossary and ADRs.
  - [x] Design spec reviewed by a subagent.
  - [ ] The owner merges the PR.

## BOOT-002 — Stage 0 plan
- **Type:** plan · **Status:** `ready` · **Depends on:** BOOT-001
- **Criteria:**
  - [ ] Plan in `docs/superpowers/plans/` with small, verifiable tasks (`writing-plans` skill).

## BOOT-003 — MCP spike: per-agent token
- **Type:** spike · **Status:** `ready` · **Depends on:** BOOT-001
- **Criteria:**
  - [ ] A minimal MCP server over HTTP requires `Authorization: Bearer` and Claude Code connects from `.mcp.json` on Windows.
  - [ ] It is checked whether a subagent can carry its own token or inherits the session's.
  - [ ] Result recorded in ADR-0005 (accepted or superseded). The spike code is discarded.

## BOOT-004 — Repo foundations
- **Type:** chore · **Status:** `ready` · **Depends on:** BOOT-002
- **Criteria:**
  - [ ] `uv` installed and `backend/` with tooling (Ruff, pyright, pytest).
  - [ ] `frontend/` with Vite, Biome and Vitest.
  - [ ] A single `check` command that runs both sides and fails if anything fails.
  - [ ] Docker "hello world" with a named volume and the port only on `127.0.0.1`.

## BOOT-005 — CI, Dependabot and PR template
- **Type:** ci · **Status:** `ready` · **Depends on:** BOOT-004
- **Criteria:**
  - [ ] GitHub Actions workflow that runs `check` (job `check`).
  - [ ] `dependabot.yml` for `pip`, `npm`, `docker` and `github-actions`, targeting `main`.
  - [ ] PR template in English.
  - [ ] The owner imports the `main` ruleset on GitHub.
