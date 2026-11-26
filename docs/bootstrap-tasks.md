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
- **Type:** chore · **Status:** `done` · **Branch:** `chore/BOOT-004-foundations` (PR #6) · **Plan:** Tasks 2–5 · **Depends on:** BOOT-001
- **Criteria:**
  - [x] `uv` installed (with the owner's consent) and `backend/` with a tested health endpoint, Ruff, pyright and pytest.
  - [x] `frontend/` with a PWA skeleton, Biome and Vitest, and UI strings in a message catalog.
  - [x] TypeScript API types generated from OpenAPI, with a drift check that survives Windows line endings.
  - [x] A single `check` command that runs everything and fails if anything fails.

## BOOT-005 — CI, Dependabot and PR template
- **Type:** ci · **Status:** `in_progress` · **Branch:** `ci/BOOT-005-ci` (PR #9 merged; only the ruleset import is left) · **Plan:** Task 9 · **Depends on:** BOOT-004, BOOT-006
- **Criteria:**
  - [x] GitHub Actions workflow with a job named `check` and a Docker smoke job.
  - [x] `dependabot.yml` for `uv`, `npm`, `docker` and `github-actions`, targeting `main`.
  - [x] PR template in English.
  - [ ] The owner imports the `main` ruleset on GitHub (Claude prepares the JSON).

## BOOT-006 — Docker image and compose
- **Type:** build · **Status:** `done` · **Branch:** `build/BOOT-006-docker` (PR #7) · **Plan:** Task 6 · **Depends on:** BOOT-004
- **Criteria:**
  - [x] Multi-stage image, non-root, read-only filesystem, healthcheck.
  - [x] Compose publishes the port only on `127.0.0.1` and keeps data in a named volume, both enforced by tests.
  - [x] A fresh volume is writable by the non-root user; image size and idle RAM recorded.
  - Measured: image **224 MB**, idle RAM **45 MiB** (both under the 300 MB / 200 MiB flags).

## BOOT-007 — Claude Code project configuration
- **Type:** chore · **Status:** `done` · **Branch:** `chore/BOOT-007-claude-config` (PR #8) · **Plan:** Tasks 7–8 · **Depends on:** BOOT-004
- **Criteria:**
  - [x] Hooks that block destructive commands (including `gh pr merge`), remind about `docs/STATUS.md` and format on edit, all unit-tested.
  - [x] Project agents (orchestrator, backend, frontend, bugs, reviewer), path-scoped rules and two skills, with a structural test.

## BOOT-008 — Stage 1 decomposition design
- **Type:** docs · **Status:** `done` · **Branch:** `docs/BOOT-008-stage-1-design` (PR #11) · **Depends on:** BOOT-004..007
- **Criteria:**
  - [x] Stage 1 cut into slices, with the order chosen by the owner (by layers).
  - [x] Technical decisions of slice 1 (pure domain) written down as proposals.
  - [x] The owner approves the design and merges the PR.

## BOOT-009 — Back to Node 24 and ignore Node majors
- **Type:** build · **Status:** `done` · **Branch:** `ci/BOOT-009-dependabot-node` (PR #12) · **Depends on:** BOOT-005
- **Criteria:**
  - [x] Dockerfile back on `node:24-slim`; image builds and answers `/api/health`.
  - [x] Dependabot ignores `node` semver-major updates.
  - [x] The owner merges PR #12.

## BOOT-010 — Stage 1 slice 1 plan (pure domain)
- **Type:** plan · **Status:** `done` · **Branch:** `docs/BOOT-010-slice-1-plan` (PR #13) · **Depends on:** BOOT-008
- **Criteria:**
  - [x] Plan in `docs/superpowers/plans/` with exact interfaces, tests and review focus.
  - [x] The owner reviews the plan and merges the PR.

## BOOT-011 to BOOT-013 — Slice 1: pure domain
- **Type:** feat · **Status:** `in_progress` · **Plan:** Tasks 1–9 of the slice 1 plan · **Depends on:** BOOT-010
- **Criteria:**
  - [x] PR A (in review): vocabulary, dependency graph, progress, gates (BOOT-011).
  - [ ] PR B: transition policy and assignment (BOOT-012).
  - [ ] PR C: task changes, approval requests, visibility and property-based invariants (BOOT-013).
