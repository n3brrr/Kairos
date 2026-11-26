# Kairos status

> **Read this first.** If context was lost, this file says where we are. Rewrite it (do not append) when closing each block of work.

**Last updated:** 2026-11-26 · **Phase:** stage 1, slice 1 (pure domain) built; its three PRs are in review.

## Where we are

- **Stage 0 is done in `main`:** backend and frontend skeletons, contract pipeline (OpenAPI → TypeScript, drift-checked), the single `check` command, Docker image and compose (224 MB, 45 MiB idle RAM), Claude Code project config (hooks, five agents, three path-scoped rules, two skills), and CI (`check` and `docker` jobs, Dependabot, PR template). PRs #1 to #9 are merged. The owner confirmed the project hooks load (`/hooks`). The `/agents` wizard no longer exists in Claude Code 2.1.332: agents are just the files in `.claude/agents/`.
- **Stage 1 is cut into six slices** (design: [`superpowers/specs/2026-11-26-stage-1-decomposition-design.md`](superpowers/specs/2026-11-26-stage-1-decomposition-design.md)). The owner chose "by layers": 1 pure domain, 2 persistence and history, 3 REST and owner login, 4 MCP, agents and tokens, 5 minimal UI, 6 dogfood. Each slice gets its own plan and PRs.
- The stage 1 design (PR #11) and the slice 1 plan (PR #13) are merged, and so is the Node 24 fix (PR #12): `main` is green and the `main` ruleset is imported (squash only, `check` required).
- **Slice 1 (the pure domain) is built** in the worktree `Kairos-wt/BOOT-011` as three stacked PRs (plan: [`superpowers/plans/2026-11-26-stage-1-slice-1-domain.md`](superpowers/plans/2026-11-26-stage-1-slice-1-domain.md)): **PR A** (#14, vocabulary, dependency graph and progress, gates), **PR B** (#15, the transition policy as one data table, assignment and the queue) and **PR C** (task creation and changes, evidence, comments, dependencies, approval requests, visibility, property-based invariants). `backend/src/kairos/domain/` is pure (a test enforces stdlib-only imports). 437 backend tests; `python tools/check.py` passes.
- **How strong the tests are:** the policy test walks every (status, status, actor kind) triple against a hand-written copy of design §6.3. A stateful Hypothesis model plays the use cases and checks the invariants after every step. I mutation-checked them: nine deliberate rule breaks (an agent approving, the busy-agent rule overridable, backward moves keeping the assignment, the review gate ignoring evidence, evidence smuggled through the criteria field, retyping an assigned task, submitting another agent's task, and others) each fail the suite. The first version of the model never reached `IN_PROGRESS`; that was found and fixed.
- **Independent review of the whole slice** found 1 Critical and 6 Important issues, all fixed test-first except one that needs the owner (see below). The Critical one: evidence could be written through the `criteria` field, bypassing the evidence gate.
- **Decisions beyond the plan** (ledger R1 to R13; the ones that change the spec are now written in §6.4 and §6.5): the one-in-progress rule per agent is an invariant nobody can override, the owner included; the queue limit is checked at assignment only; evidence only enters through `decide_attach_evidence`; a task's type cannot change while it is assigned; `created_by` grants visibility only while a task is unassigned.
- Nothing is running. A leftover empty dev volume `boot-006_kairos-data` exists on the owner's Docker; it can be removed with `docker volume rm boot-006_kairos-data`.

## What the spike decided (ADR-0005)

- Per-agent token works: `Authorization: Bearer ${KAIROS_TOKEN}` from `.mcp.json` is sent on Windows (Claude Code 2.1.332).
- Subagents share the session identity by default (attributed with `via`).
- A subagent can carry its own token only as an opt-in, verified through `--agents` only. The agent-file route (`.claude/agents/*.md` in a trusted folder) is **unverified**; it is part of slice 4. Its step "run `/agents`" is obsolete: check the agent through the `@agent-` autocomplete instead.

## Next (in order)

1. The owner merges PR A (#14), then PR B (#15), then PR C, in that order (**Squash and merge**). After each I merge `origin/main` into the next branch and retarget its PR.
2. Slice 2 (persistence and history): SQLite, Alembic, repositories, use cases that apply the domain decisions, the hash-chained `events` log. Brainstorm what is open, then write its plan.
3. Slices 3 to 6, one plan each, in order.

## Waiting on the owner

- Merge PR A, B and C in order (**Squash and merge**).
- **Decide how agents finish tasks that have subtasks.** Today an agent cannot: the spec says a subtask belongs to whoever carries the task (§6.1) but §6.5 does not list subtasks among what an agent may change, and the review gate requires none pending. I did not let agents edit `subtasks` because they are a tuple of statuses with no identity, so editing would also allow deleting a pending one and skipping the gate. Proposal: in slice 2 subtasks become items with ids, and the carrier may only tick them done. Tell me if you want a different rule.

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
- **Slice 2 must remember these domain findings** (also in the ledger): (1) `decide_transition` from `IN_REVIEW` to `DONE`/`READY` does not touch the pending delivery request: approving or returning a delivery must go through `decide_resolve_request`, or the request stays pending; (2) the use case computes `GateContext`, `queue_load` and the dependency map, so those queries must match the domain's definitions; (3) an orchestrator profile can be assigned a task that the orchestrator can never start; (4) field values are not validated by the domain (priority, labels, dates): Pydantic does that at the edges; (5) `Task.project_id` cannot change.
- **Deferred minor findings from stage 0** (ledger): `check.py` crashes with a traceback if `uv` or `pnpm` is missing; the SPA catch-all is GET-only; `/docs`, `/redoc` and `/openapi.json` are public until auth lands (slice 3); pyright does not cover `tools/`.
