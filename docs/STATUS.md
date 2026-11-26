# Kairos status

> **Read this first.** If context was lost, this file says where we are. Rewrite it (do not append) when closing each block of work.

**Last updated:** 2026-11-26 · **Phase:** stage 1, slice 1 (pure domain) in execution: PR A and PR B are in review.

## Where we are

- **Stage 0 is done in `main`:** backend and frontend skeletons, contract pipeline (OpenAPI → TypeScript, drift-checked), the single `check` command, Docker image and compose (224 MB, 45 MiB idle RAM), Claude Code project config (hooks, five agents, three path-scoped rules, two skills), and CI (`check` and `docker` jobs, Dependabot, PR template). PRs #1 to #9 are merged. The owner confirmed the project hooks load (`/hooks`). The `/agents` wizard no longer exists in Claude Code 2.1.332: agents are just the files in `.claude/agents/`.
- **Stage 1 is cut into six slices** (design: [`superpowers/specs/2026-11-26-stage-1-decomposition-design.md`](superpowers/specs/2026-11-26-stage-1-decomposition-design.md)). The owner chose "by layers": 1 pure domain, 2 persistence and history, 3 REST and owner login, 4 MCP, agents and tokens, 5 minimal UI, 6 dogfood. Each slice gets its own plan and PRs.
- The stage 1 design (PR #11) and the slice 1 plan (PR #13) are merged, and so is the Node 24 fix (PR #12): `main` is green and the `main` ruleset is imported (squash only, `check` required).
- **Slice 1 runs in the worktree `Kairos-wt/BOOT-011`** as three stacked PRs (plan: [`superpowers/plans/2026-11-26-stage-1-slice-1-domain.md`](superpowers/plans/2026-11-26-stage-1-slice-1-domain.md)). **PR A** (#14, `feat/BOOT-011-domain-model`, Tasks 1 to 4): vocabulary, dependency graph and progress, gates. **PR B** (`feat/BOOT-012-domain-policy`, Tasks 5 and 6, stacked on A): the transition policy as one data table (`TRANSITION_RULES`) checked against a hand-written copy of design §6.3 for every status pair and actor kind, owner gate override with a recorded reason, assignment and the queue (`queue_load`). `backend/src/kairos/domain/` stays pure (a test enforces stdlib-only imports). PR C (task changes, approval requests, visibility, property-based invariants) comes next.
- Rulings that went beyond the plan (ledger R1 to R6): `AGENT_BUSY` is a hard invariant nobody can override and also binds the owner; backward moves into `IN_PROGRESS` are gated; cancelled-blocker warnings only on moves that check dependencies; `queue_load` helper added.
- The execution ledger (git-ignored scratch) is at `Kairos-wt/BOOT-011/.superpowers/sdd/2026-11-26-stage-1-slice-1-domain/progress.md`.
- Nothing is running. A leftover empty dev volume `boot-006_kairos-data` exists on the owner's Docker; it can be removed with `docker volume rm boot-006_kairos-data`.

## What the spike decided (ADR-0005)

- Per-agent token works: `Authorization: Bearer ${KAIROS_TOKEN}` from `.mcp.json` is sent on Windows (Claude Code 2.1.332).
- Subagents share the session identity by default (attributed with `via`).
- A subagent can carry its own token only as an opt-in, verified through `--agents` only. The agent-file route (`.claude/agents/*.md` in a trusted folder) is **unverified**; it is part of slice 4. Its step "run `/agents`" is obsolete: check the agent through the `@agent-` autocomplete instead.

## Next (in order)

1. The owner merges PR A, then PR B (Squash and merge, in that order).
2. PR C: Tasks 7 to 9, then one independent review of the whole slice before PR C is merged.
3. Slices 2 to 6, one plan each, in order.

## Waiting on the owner

- Merge PR A (#14), then PR B (**Squash and merge**, in that order). After each, I merge `origin/main` into the next branch and retarget its PR to `main`.

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
- **Deferred minor findings from stage 0** (ledger): `check.py` crashes with a traceback if `uv` or `pnpm` is missing; the SPA catch-all is GET-only; `/docs`, `/redoc` and `/openapi.json` are public until auth lands (slice 3); pyright does not cover `tools/`.
