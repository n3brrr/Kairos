# Roadmap

Status: ⬜ pending · 🟦 in progress · ✅ done. The detail of each stage lives in its plan (`docs/superpowers/plans/`).

## Stage −1: Design — ✅

Brainstorming, spec, ADRs, repo context. **Exits when the owner approves the spec.**

## Stage 0: Foundations and spike — 🟦

Plan: [`superpowers/plans/2026-11-26-stage-0-foundations.md`](superpowers/plans/2026-11-26-stage-0-foundations.md) (nine tasks, five PRs, spike first).

- Tooling: `uv` + `pyproject`, `pnpm` + Vite, a single `check` command (lint, types, tests on both sides).
- Repo skeleton following the map in `CLAUDE.md`; Docker "hello world" with a named volume and the port on `127.0.0.1`.
- `.claude/`: base agents, path-scoped rules, hooks (formatting, blocking destructive commands, a reminder to update `STATUS.md`).
- CI (GitHub Actions) + Dependabot + PR template, in their own PR. The `main` ruleset (imported by the owner).
- **MCP spike** (throwaway) — ✅ done (PR #4, ADR-0005): per-agent token works on Windows; a per-subagent token is an opt-in verified only through `--agents`.

**Milestone:** `check` is green in CI and the spike answers the two questions in ADR-0005.

## Stage 1: "Dogfood-ready" core — ⬜

- Pure domain: statuses, gates, permissions, invariants (with property-based tests).
- SQLite persistence + hash-chained immutable history.
- REST API and MCP server with identities and tokens; orchestrator agent.
- Full hierarchy, dependency and date model (gates and agent context need it), without rich views.
- Minimal UI: owner login, simple task list, **approval queue**, agent and token management.
- Migrate `bootstrap-tasks.md` into Kairos.

**Milestone:** the agents use Kairos to track Kairos's own tasks.

## Stage 2: Board and dashboard — ⬜

- Filterable kanban (project, type, status, agent) with progress %.
- Views for hierarchy, dependencies and semantic dates (the model already exists since stage 1).
- Dashboard (see spec §10) and live updates (SSE).
- "Mythological but simple" look (designed with mockups before implementing it).

## Stage 3: Automations — ⬜

- JSON workflow engine (trigger → conditions → actions), scheduling (cron), reminders and notifications, webhooks.
- Three editing modes over the same JSON: visual builder, declarative file and API (agents).

## Stage 4: Execution and hardening — ⬜

- Host runner to launch agents (Claude Code CLI) from automations, with limits and prior approval.
- Passkeys, scheduled backups and restore, portfolio README, passes over `FEATURES.md`.
