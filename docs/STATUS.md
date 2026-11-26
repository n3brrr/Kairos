# Kairos status

> **Read this first.** If context was lost, this file says where we are. Rewrite it (do not append) when closing each block of work.

**Last updated:** 2026-11-26 (end of day) · **Phase:** stage 0 in progress, stopped at a safe point after Task 2 of 9.

## Where we are

- `main` has the project context, the design spec and the ADRs (PR #1, merged by the owner).
- PR #3 (the stage 0 plan) and PR #4 (Task 1, the MCP spike; ADR-0005 is `accepted`) are **merged** by the owner, so `main` has them.
- **Branch `chore/BOOT-004-foundations`** (pushed, **no PR yet**): Task 2 (backend skeleton: FastAPI app factory, `/api/health`, Host validation, SPA fallback; 30 tests, Ruff and pyright strict clean) is done and reviewed. Tasks 3–5 remain; open the PR when Task 5 is done.
- Tasks 1–2 were run subagent-driven because the owner chose it for that day. **From now on the default is native** (see below).
- Nothing is running: no servers, no containers. Docker Desktop is currently **not started**; Task 6 needs it.

## What the spike decided (ADR-0005)

- Per-agent token works: `Authorization: Bearer ${KAIROS_TOKEN}` from `.mcp.json` is sent on Windows (Claude Code 2.1.332).
- Subagents share the session identity by default (attributed with `via`).
- A subagent can carry its own token only as an opt-in, verified through `--agents` only. The agent-file route (`.claude/agents/*.md` in a trusted folder) is **unverified**; stage 1 has a verification item for it.

## Next (in order)

1. **Task 3**: frontend skeleton (`frontend/`, pnpm only), on branch `chore/BOOT-004-foundations`.
2. Tasks 4 (contract pipeline) and 5 (`check` command); then push and open the BOOT-004 PR.
3. Then the stacked branches in the plan: BOOT-006 Docker, BOOT-007 Claude config, BOOT-005 CI.

## Waiting on the owner

- Merge the PR that carries this file. Squash is preferred (`CLAUDE.md`); PRs #1, #3 and #4 were merged with merge commits, which a `required_linear_history` ruleset would reject, so decide whether to keep that rule.
- Start Docker Desktop before Task 6.
- Once CI exists: import the `main` ruleset (Claude prepares the JSON).

## How to resume ("continúa por donde lo dejaste")

Default execution mode is **native**: Claude does the tasks itself with `superpowers:executing-plans`, then one independent reviewer checks the whole branch. Subagent-driven only if the owner asks again.

1. Read this file, then `CLAUDE.md`, then the plan: `docs/superpowers/plans/2026-11-26-stage-0-foundations.md`.
2. Run `gh pr list` to see what the owner merged. If `main` moved, merge it into the working branch with `git merge origin/main` (never rebase a published branch).
3. Work in the execution worktree `D:\FuckEstudios\Idiomas\Kairos-wt\stage0`, branch `chore/BOOT-004-foundations`. Push with `git push -u origin <branch>` only; never a plain `git push`.
4. The ledger of the subagent-driven part is at `D:\FuckEstudios\Idiomas\Kairos-wt\stage0\.superpowers\sdd\2026-11-26-stage-0-foundations\progress.md` (git-ignored scratch). It holds the pre-flight scan, the rulings and the deferred Minor findings for the final review. If it is lost, rebuild from `git log` and the plan.
5. Rulings still in force: `docs/STATUS.md`, `docs/bootstrap-tasks.md` and `docs/ROADMAP.md` are updated only by the controller, never by task commits; **pnpm only** for JavaScript/TypeScript, **uv** for Python (prefix `C:\Users\nebur\AppData\Local\Microsoft\WinGet\Links` on PATH when `uv` is not found); the dev dependency is `httpx2`, not `httpx` (verified: author Tom Christie, repo `pydantic/httpx2`); Biome must ignore `frontend/src/api/schema.d.ts`; use Git Bash for `curl`.
6. Update this file when the next block is done.

## Open risks

- **Agent-file subagent token** (see above): unverified. Until verified, subagents are the same agent with `via` attribution.
- **Two languages:** the backend/frontend contract depends on generating types from OpenAPI (ADR-0001); drift is checked in `check` and CI.
- **Claude Pro quota:** subagent-driven runs and the spike spend it; native is the default for that reason.
- **Deferred minor findings** from the Task 2 review (listed in the ledger) go to the final whole-branch review.
