# Kairos status

> **Read this first.** If context was lost, this file says where we are. Rewrite it (do not append) when closing each block of work.

**Last updated:** 2026-11-26 · **Phase:** design closed; stage 0 plan written, waiting for the owner's review.

## Where we are

- Concept, scope and stack were defined with the owner and documented in [`superpowers/specs/2026-11-26-kairos-design.md`](superpowers/specs/2026-11-26-kairos-design.md). No open questions remain.
- Remote connected: <https://github.com/n3brrr/Kairos> (public, MIT, `main` not protected yet).
- PR #1 (`docs/BOOT-001-project-context`) brings the context and the spec to `main`; **the owner merges it** (squash).
- PR #2 (`docs/BOOT-002-stage0-plan`, stacked on #1) adds the stage 0 plan: [`superpowers/plans/2026-11-26-stage-0-foundations.md`](superpowers/plans/2026-11-26-stage-0-foundations.md).
- **There is no product code.** Execution starts once the owner reviews the plan and picks the execution method.
- Language policy (owner, 2026-11-26): chat with the owner in Spanish; everything else in English, UI included.

## Done

- Brainstorming: requirements, agent limits, orchestrator, stack (Python backend + React frontend), trunk-based git flow.
- Repo context: `CLAUDE.md`, `docs/`, ADRs 0001–0006, `.gitignore`, `.gitattributes`, `.editorconfig`.
- Design spec reviewed by a subagent and closed with the owner's answers.
- Stage 0 plan: nine tasks in five PRs (spike first).

## Next (in order)

1. The owner merges PR #1, reviews PR #2 and chooses the execution method (subagent-driven or native).
2. Stack note: PR #2 is stacked on PR #1's branch. After PR #1 is squash-merged, run `git rebase --onto origin/main <old PR #1 tip> docs/BOOT-002-stage0-plan` and retarget PR #2 to `main`.
3. Execute the plan: Task 1 (MCP spike) first, then Tasks 2–5, 6, 7–8, 9.

## Waiting on the owner

- Merge PR #1 (squash) and review PR #2.
- Choose the execution method for the plan.
- Allow installing `uv` (not installed) when the plan reaches it.
- Once CI exists: import the `main` ruleset on GitHub (Settings → Rules → Rulesets → Import). Claude prepares the JSON.

## Open risks

- **MCP + per-agent token on Windows:** there are reports that Claude Code ignores the `Authorization` header when the server advertises OAuth, and of failures with a project `.mcp.json` on Windows. The spike (plan Task 1) validates this (ADR-0005).
- **Can a subagent carry its own token or does it inherit the session's?** Until proven otherwise they are treated as the same agent, with attribution (`via`).
- **Two languages:** the backend/frontend contract depends on generating types from OpenAPI (ADR-0001); drift is checked in `check` and CI.
- **Claude Pro quota:** the spike and any agent run spend it; keep experiments few.

## How to resume

1. Read this file, then `CLAUDE.md`, then the current spec and plan.
2. `git status` and `git log --oneline -10` to see the real state.
3. Check `docs/bootstrap-tasks.md` for the next task.
4. When the block is done: rewrite this file.
