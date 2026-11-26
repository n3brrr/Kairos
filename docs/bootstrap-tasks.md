# Bootstrap tasks

Kairos does not exist yet, so its first tasks live here. They use the same format they will have in Kairos (type, status, criteria) so they can be migrated without rewriting. In stage 1 they are imported into Kairos and this file stays as history. The detail of each task is in the stage 0 plan: [`superpowers/plans/2026-11-26-stage-0-foundations.md`](superpowers/plans/2026-11-26-stage-0-foundations.md).

Statuses: `ready` · `in_progress` · `in_review` · `done`. IDs: `BOOT-nn`.

## BOOT-001 — Project context in the repo
- **Type:** docs · **Status:** `done` · **Branch:** `docs/BOOT-001-project-context` (merged in PR #1)
- **Criteria:**
  - [x] `CLAUDE.md` with map, golden rules and git flow.
  - [x] `docs/` with status, roadmap, ideas, glossary and ADRs.
  - [x] Design spec reviewed by a subagent.
  - [x] The owner merges the PR.

## BOOT-002 — Stage 0 plan
- **Type:** plan · **Status:** `done` · **Branch:** `docs/BOOT-002-stage0-plan` (merged in PR #3) · **Depends on:** BOOT-001
- **Criteria:**
  - [x] Plan in `docs/superpowers/plans/` with small, verifiable tasks (`writing-plans` skill).
  - [x] The owner reviews the plan and chooses the execution method (subagent-driven for the first day, native by default afterwards).

## BOOT-003 — MCP spike: per-agent token
- **Type:** spike · **Status:** `done` · **Branch:** `docs/BOOT-003-mcp-spike-result` (merged in PR #4) · **Plan:** Task 1 · **Depends on:** BOOT-001
- **Criteria:**
  - [x] A minimal MCP server over HTTP requires `Authorization: Bearer` and Claude Code connects from `.mcp.json` on Windows.
  - [x] It is checked whether a subagent can carry its own token or inherits the session's.
  - [x] Result recorded in ADR-0005 (accepted or superseded). The spike code is discarded.
  - [x] The owner merges PR #4.

## BOOT-004 — Tooling and `check`
- **Type:** chore · **Status:** `in_review` · **Branch:** `chore/BOOT-004-foundations` · **Plan:** Tasks 2–5 · **Depends on:** BOOT-001
- **Criteria:**
  - [x] `uv` installed (with the owner's consent) and `backend/` with a tested health endpoint, Ruff, pyright and pytest.
  - [x] `frontend/` with a PWA skeleton, Biome and Vitest, and UI strings in a message catalog.
  - [x] TypeScript API types generated from OpenAPI, with a drift check that survives Windows line endings.
  - [x] A single `check` command that runs everything and fails if anything fails.

## BOOT-005 — CI, Dependabot and PR template
- **Type:** ci · **Status:** `ready` · **Plan:** Task 9 · **Depends on:** BOOT-004, BOOT-006
- **Criteria:**
  - [ ] GitHub Actions workflow with a job named `check` and a Docker smoke job.
  - [ ] `dependabot.yml` for `uv`, `npm`, `docker` and `github-actions`, targeting `main`.
  - [ ] PR template in English.
  - [ ] The owner imports the `main` ruleset on GitHub (Claude prepares the JSON).

## BOOT-006 — Docker image and compose
- **Type:** build · **Status:** `in_review` · **Branch:** `build/BOOT-006-docker` · **Plan:** Task 6 · **Depends on:** BOOT-004
- **Criteria:**
  - [x] Multi-stage image, non-root, read-only filesystem, healthcheck.
  - [x] Compose publishes the port only on `127.0.0.1` and keeps data in a named volume, both enforced by tests.
  - [x] A fresh volume is writable by the non-root user; image size and idle RAM recorded.
  - Measured: image **224 MB**, idle RAM **45 MiB** (both under the 300 MB / 200 MiB flags).

## BOOT-007 — Claude Code project configuration
- **Type:** chore · **Status:** `ready` · **Plan:** Tasks 7–8 · **Depends on:** BOOT-004
- **Criteria:**
  - [ ] Hooks that block destructive commands (including `gh pr merge`), remind about `docs/STATUS.md` and format on edit, all unit-tested.
  - [ ] Project agents (orchestrator, backend, frontend, bugs, reviewer), path-scoped rules and two skills, with a structural test.
