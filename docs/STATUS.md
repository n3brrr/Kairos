# Kairos status

> **Read this first.** If context was lost, this file says where we are. Rewrite it (do not append) when closing each block of work.

**Last updated:** 2026-11-26 · **Phase:** stage 1 in progress: the slice 1 (pure domain) plan is in review.

## Where we are

- **Stage 0 is done in `main`:** backend and frontend skeletons, contract pipeline (OpenAPI → TypeScript, drift-checked), the single `check` command, Docker image and compose (224 MB, 45 MiB idle RAM), Claude Code project config (hooks, five agents, three path-scoped rules, two skills), and CI (`check` and `docker` jobs, Dependabot, PR template). PRs #1 to #9 are merged. The owner confirmed the project hooks load (`/hooks`). The `/agents` wizard no longer exists in Claude Code 2.1.332: agents are just the files in `.claude/agents/`.
- **Stage 1 is cut into six slices** (design: [`superpowers/specs/2026-11-26-stage-1-decomposition-design.md`](superpowers/specs/2026-11-26-stage-1-decomposition-design.md)). The owner chose "by layers": 1 pure domain, 2 persistence and history, 3 REST and owner login, 4 MCP, agents and tokens, 5 minimal UI, 6 dogfood. Each slice gets its own plan and PRs.
- The stage 1 design (BOOT-008, PR #11) is merged. **Branch `docs/BOOT-010-slice-1-plan`** (worktree `Kairos-wt/BOOT-010`) carries the slice 1 plan: [`superpowers/plans/2026-11-26-stage-1-slice-1-domain.md`](superpowers/plans/2026-11-26-stage-1-slice-1-domain.md). Nine tasks in three stacked PRs: A (BOOT-011: vocabulary, dependency graph, gates), B (BOOT-012: transition policy, assignment), C (BOOT-013: task changes, approval requests, visibility, property-based invariants). No domain code exists yet.
- **`main` is red** since the Dependabot PR #10 (Node 25) was merged: Node 25 has no `corepack`, so the image build fails. **PR #12** returns the Dockerfile to `node:24-slim` and makes Dependabot ignore Node major bumps; its CI is green. Merge it first.
- Nothing is running. A leftover empty dev volume `boot-006_kairos-data` exists on the owner's Docker; it can be removed with `docker volume rm boot-006_kairos-data`.

## What the spike decided (ADR-0005)

- Per-agent token works: `Authorization: Bearer ${KAIROS_TOKEN}` from `.mcp.json` is sent on Windows (Claude Code 2.1.332).
- Subagents share the session identity by default (attributed with `via`).
- A subagent can carry its own token only as an opt-in, verified through `--agents` only. The agent-file route (`.claude/agents/*.md` in a trusted folder) is **unverified**; it is part of slice 4. Its step "run `/agents`" is obsolete: check the agent through the `@agent-` autocomplete instead.

## Next (in order)

1. The owner merges PR #12 (fixes `main`) and this plan's PR.
2. Execute the plan natively (`executing-plans`), PR A first, one independent review of the whole slice before the last PR is merged.
3. Slices 2 to 6, one plan each, in order.

## Waiting on the owner

- **Merge PR #12** (Squash and merge): it repairs the red `docker` job on `main`.
- Merge the BOOT-010 plan PR (Squash and merge). Please read the "My calls" section of the plan: they are proposals (assignment rules, queue counting, who creates what).
- **Import the `main` ruleset** if not done yet (check with `gh api repos/n3brrr/Kairos/rulesets`; `[]` means not imported): file `D:\FuckEstudios\Idiomas\Kairos-wt\protect-main.ruleset.json` (outside the repo), via GitHub → Settings → Rules → Rulesets → New ruleset → Import a ruleset. It would also have blocked the Node 25 merge, since `check` and `docker` were not both green.

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
