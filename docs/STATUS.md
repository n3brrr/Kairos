# Kairos status

> **Read this first.** If context was lost, this file says where we are. Rewrite it (do not append) when closing each block of work.

**Last updated:** 2026-11-26 · **Phase:** stage 0 in progress; all 9 tasks done; BOOT-005 (CI) awaiting its merge, then the `main` ruleset.

## Where we are

- `main` has the project context, the design spec and the ADRs (PR #1, merged by the owner).
- PRs #1, #3 (plan), #4 (MCP spike, ADR-0005 `accepted`), #6 (BOOT-004: skeletons, contract pipeline, `check`), #7 (BOOT-006: Docker image and compose) and #8 (BOOT-007: hooks, agents, rules, skills) are **merged**; `main` has them.
- The owner confirmed the project hooks load (`/hooks` shows the three project hooks). The five agents and two skills appear in the session. The `/agents` wizard no longer exists in Claude Code 2.1.332: agents are just the files in `.claude/agents/`.
- **Branch `ci/BOOT-005-ci`** (PR #9, worktree `Kairos-wt/BOOT-005`): Task 9 done: workflow with jobs `check` (runs all 10 `check` steps, `UV_LOCKED=1`) and `docker` (compose smoke test), Dependabot (TypeScript majors ignored), PR template. **Its first CI run passed both jobs**, and the log shows all 10 steps `PASS`.
- Nothing is running. A leftover empty dev volume `boot-006_kairos-data` exists on the owner's Docker; it can be removed with `docker volume rm boot-006_kairos-data`.

## What the spike decided (ADR-0005)

- Per-agent token works: `Authorization: Bearer ${KAIROS_TOKEN}` from `.mcp.json` is sent on Windows (Claude Code 2.1.332).
- Subagents share the session identity by default (attributed with `via`).
- A subagent can carry its own token only as an opt-in, verified through `--agents` only. The agent-file route (`.claude/agents/*.md` in a trusted folder) is **unverified**; stage 1 has a verification item for it.

## Next (in order)

1. The owner merges PR #9 (squash), then imports the `main` ruleset.
2. Stage 0 is then complete. Next is stage 1 (the board core and the MCP endpoint, `docs/ROADMAP.md`): it starts with a brainstorming and spec check, then its own plan. Carry in the stage 1 verification item for the agent-file subagent token (ADR-0005; note its step "run `/agents`" is obsolete: check that the agent is available through the `@agent-` autocomplete instead).

## Waiting on the owner

- Merge PR #9 (squash). After that, import the `main` ruleset: file `D:\FuckEstudios\Idiomas\Kairos-wt\protect-main.ruleset.json` (outside the repo) via GitHub → Settings → Rules → Rulesets → New ruleset → Import a ruleset. It requires a PR, the `check` status (branch up to date), linear history, and forbids force-push and deletion; 0 approvals, no bypass. Import it **after** PR #9 is merged so the required `check` is reported on every PR.
- With `required_linear_history` on, **merge commits are rejected**: from now on always use **Squash and merge** (PRs #1, #3 and #4 used merge commits).

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
