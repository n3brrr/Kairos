# Kairos status

> **Read this first.** If context was lost, this file says where we are. Rewrite it (do not append) when closing each block of work.

**Last updated:** 2026-11-26 · **Phase:** stage 1, slice 2 (persistence and history) is built; PR C (use cases) is in review.

## Where we are

- **Stage 0 is done in `main`:** backend and frontend skeletons, contract pipeline (OpenAPI → TypeScript, drift-checked), the single `check` command, Docker image and compose (224 MB, 45 MiB idle RAM), Claude Code project config (hooks, five agents, three path-scoped rules, two skills), and CI (`check` and `docker` jobs, Dependabot, PR template). PRs #1 to #9 are merged. The owner confirmed the project hooks load (`/hooks`). The `/agents` wizard no longer exists in Claude Code 2.1.332: agents are just the files in `.claude/agents/`.
- **Stage 1 is cut into six slices** (design: [`superpowers/specs/2026-11-26-stage-1-decomposition-design.md`](superpowers/specs/2026-11-26-stage-1-decomposition-design.md)). The owner chose "by layers": 1 pure domain, 2 persistence and history, 3 REST and owner login, 4 MCP, agents and tokens, 5 minimal UI, 6 dogfood. Each slice gets its own plan and PRs.
- The stage 1 design (PR #11) and the slice 1 plan (PR #13) are merged, and so is the Node 24 fix (PR #12): `main` is green and the `main` ruleset is imported (squash only, `check` required).
- **Slice 1 (the pure domain) is in `main`** (PRs #14, #15 and #16 reached it through the recovery PR #17; plan: [`superpowers/plans/2026-11-26-stage-1-slice-1-domain.md`](superpowers/plans/2026-11-26-stage-1-slice-1-domain.md)): vocabulary, dependency graph and progress, gates, the transition policy as one data table, assignment and the queue, task changes, evidence, comments, dependencies, approval requests, visibility and property-based invariants. `backend/src/kairos/domain/` is pure (a test enforces stdlib-only imports).
- **How strong the tests are:** the policy test walks every (status, status, actor kind) triple against a hand-written copy of design §6.3. A stateful Hypothesis model plays the use cases and checks the invariants after every step. I mutation-checked them: nine deliberate rule breaks (an agent approving, the busy-agent rule overridable, backward moves keeping the assignment, the review gate ignoring evidence, evidence smuggled through the criteria field, retyping an assigned task, submitting another agent's task, and others) each fail the suite. The first version of the model never reached `IN_PROGRESS`; that was found and fixed.
- **Independent review of the whole slice** found 1 Critical and 6 Important issues, all fixed test-first except one that needs the owner (see below). The Critical one: evidence could be written through the `criteria` field, bypassing the evidence gate.
- **Decisions beyond the plan** (ledger R1 to R13; the ones that change the spec are now written in §6.4 and §6.5): the one-in-progress rule per agent is an invariant nobody can override, the owner included; the queue limit is checked at assignment only; evidence only enters through `decide_attach_evidence`; a task's type cannot change while it is assigned; `created_by` grants visibility only while a task is unassigned.
- **Slice 2 (persistence and history) is in `main` except its last PR** ([plan](superpowers/plans/2026-11-26-stage-1-slice-2-persistence.md)). Merged: PR A (#19: subtasks with a kanban status, owner-only registry decisions) and PR B (#20: SQLite in WAL, Alembic baseline, partial unique indexes and triggers, the hash-chained event log, `python -m kairos.features.history` to verify it). **PR C** (branch `feat/BOOT-017-use-cases`, worktree `Kairos-wt/BOOT-017`): repositories, `TaskService` (13 use cases, each one transaction that writes the task, its request and its events together, or nothing), `RegistryService`, visibility-filtered `TaskQueries`, and the app migrating its database on startup.
- **How strong the slice 2 tests are:** the database is exercised through the use cases, not only the repositories: a full lifecycle checked event by event; an exhaustive test that no agent, subagent or orchestrator reaches `done` or `cancelled` through any move; a rolled-back decision leaves every table untouched; a stateful Hypothesis model plays the services at random (30 steps by 25 examples, with a guided walk so it reaches `done` in every example) and checks after each step: the hash chain verifies, one `in_progress` per agent, one pending request per task, a pending delivery request exists exactly while the task is in review, and every task row equals the replay of its events. Mutation checks: letting the orchestrator approve, and not writing events, are both caught.
- **Independent review of the whole slice** (opus; a first attempt on fable stopped on a usage-credits limit) found 0 Critical and 4 Important issues, all fixed test-first: a plain move out of review left the delivery request pending (now `decide_move_task` in the domain closes it and approves the subtasks in review); subtasks could change while the owner reviewed, and approval ignored open subtasks; duplicate criterion ids crashed in the database instead of being rejected; the orchestrator could delete an agent's evidence by dropping its criterion. Nine minors are deferred (ledger, listed under Open risks).
- **Measured in Docker:** the image boots, migrates to revision `0001`, seeds the five task types and `verify` answers `OK`. Cost of the database stack: 80 MiB idle RAM (was 45) and a 249 MB image (was 224).
- Nothing is running. Leftover empty dev volumes on the owner's Docker: `boot-006_kairos-data`, `boot-009_kairos-data` and `boot-017_kairos-data`; remove them with `docker volume rm <name>` when convenient (never `docker compose down -v` on the real one).

## What the spike decided (ADR-0005)

- Per-agent token works: `Authorization: Bearer ${KAIROS_TOKEN}` from `.mcp.json` is sent on Windows (Claude Code 2.1.332).
- Subagents share the session identity by default (attributed with `via`).
- A subagent can carry its own token only as an opt-in, verified through `--agents` only. The agent-file route (`.claude/agents/*.md` in a trusted folder) is **unverified**; it is part of slice 4. Its step "run `/agents`" is obsolete: check the agent through the `@agent-` autocomplete instead.

## Next (in order)

1. The owner merges PR C of slice 2 (**Squash and merge**). It is the last PR of the slice.
2. Slice 3 (REST and owner login): brainstorm what is open (CSRF and attempt-limiting details, the one-time local command that creates the owner), write its plan, then execute it natively.
3. Slices 4 to 6, one plan each, in order.

## Waiting on the owner

- Merge PR C of slice 2 (**Squash and merge**).
- Read the "My calls" of the slice 2 plan if you have not: SQLAlchemy Core without an ORM, the five seeded task types (`bug` needs a description, `feature` a description and a priority), the hash format, and the cascade (approving a delivery approves the subtasks still in review).

## How to resume ("continúa por donde lo dejaste")

Default execution mode is **native**: Claude does the tasks itself with `superpowers:executing-plans`, then one independent reviewer checks the whole branch. Subagent-driven only if the owner asks.

1. Read this file, then `CLAUDE.md`, then the stage 1 design and the current slice's plan in `docs/superpowers/plans/`.
2. Run `gh pr list` to see what the owner merged. Start every task from `origin/main` in its own worktree (`git worktree add ../Kairos-wt/<ID> -b <branch> origin/main`). Push with `git push -u origin <branch>`.
3. Rulings still in force: **pnpm only** for JavaScript/TypeScript, **uv** for Python (prefix `C:\Users\nebur\AppData\Local\Microsoft\WinGet\Links` on PATH when `uv` is not found); dev dependency `httpx2`, not `httpx`; TypeScript stays on 5.x (`openapi-typescript` crashes on 7); use Git Bash for `curl`; the project hooks block `npm`, force-push, `git add .` and `gh pr merge`.
4. The stage 0 ledger (git-ignored scratch) is at `D:\FuckEstudios\Idiomas\Kairos-wt\stage0\.superpowers\sdd\2026-11-26-stage-0-foundations\progress.md`; it holds the deferred minor findings.
5. Update this file when the next block is done.

## Open risks

- **Agent-file subagent token** (see above): unverified. Until verified, subagents are the same agent with `via` attribution.
- **Two languages:** the backend/frontend contract depends on generating types from OpenAPI (ADR-0001); drift is checked in `check` and CI.
- **Claude Pro quota:** subagent-driven runs and the spike spend it; native is the default for that reason.
- **Deferred minor findings from slice 2** (ledger): the engine URL breaks on a `%` in the data folder name; subtask row ids `<task>:<subtask>` can collide when ids contain `:`; blank task and subtask ids are accepted; "insertion order" relies on `rowid`; `UnitOfWork` leaks a connection if `BEGIN IMMEDIATE` times out and the lifespan does not dispose the engine if the migration fails; `verify` prints a traceback when `kairos.db` has no `events` table; a lone surrogate in a comment raises instead of being rejected (the Pydantic edges should refuse it); an agent can probe ids through `ALREADY_EXISTS` (server-generated ids fix it); every transaction, reads included, takes the write lock; agent profiles may use the ids `owner` or `system`.
- **Slice 3 and 4 must remember** (domain findings, also in the ledger): an orchestrator profile can be assigned a task it can never start; `Actor.kind` is not cross-checked with the stored profile kind (slice 4 builds actors from tokens, so it must); field values are not validated by the domain (priority, labels, dates): Pydantic does that at the edges; `Task.project_id` cannot change; `fields_updated` records field names, not values.
- **Deferred minor findings from stage 0** (ledger): `check.py` crashes with a traceback if `uv` or `pnpm` is missing; the SPA catch-all is GET-only; `/docs`, `/redoc` and `/openapi.json` are public until auth lands (slice 3); pyright does not cover `tools/`.
