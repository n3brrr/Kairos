# Kairos status

> **Read this first.** If context was lost, this file says where we are. Rewrite it (do not append) when closing each block of work.

**Last updated:** 2026-11-26 · **Phase:** design closed; stage 0 plan in progress.

## Where we are

- Concept, scope and stack were defined with the owner and documented in [`superpowers/specs/2026-11-26-kairos-design.md`](superpowers/specs/2026-11-26-kairos-design.md). A subagent review of the spec left two questions; the owner answered them (spec §17.1). No open questions remain.
- Remote connected: <https://github.com/n3brrr/Kairos> (public, MIT, `main` not protected yet).
- PR `docs/BOOT-001-project-context` brings this context to `main`; **the owner merges it** (squash).
- **There is no product code.** The next step is the stage 0 plan (`writing-plans`).
- Language policy (owner, 2026-11-26): chat with the owner in Spanish; everything else in English, UI included.

## Done

- Brainstorming: requirements, agent limits, orchestrator, stack (Python backend + React frontend), trunk-based git flow.
- Repo context: `CLAUDE.md`, `docs/`, ADRs 0001–0006, `.gitignore`, `.gitattributes`, `.editorconfig`.
- Design spec reviewed by a subagent and closed with the owner's answers.

## Next (in order)

1. The owner reviews and merges the BOOT-001 PR.
2. Stage 0 plan in `docs/superpowers/plans/` (BOOT-002).
3. Execute stage 0: tooling, `check`, Docker, `.claude/`, CI. Then the MCP spike (ADR-0005).

## Waiting on the owner

- Merge the BOOT-001 PR (squash).
- Once CI exists: import the `main` ruleset on GitHub (Settings → Rules → Rulesets → Import). Claude prepares the JSON.
- If the plan requires it: confirm installing `uv` (not installed).

## Open risks

- **MCP + per-agent token on Windows:** there are reports that Claude Code ignores the `Authorization` header when the server advertises OAuth, and of failures with a project `.mcp.json` on Windows. The spike validates this (ADR-0005).
- **Can a subagent carry its own token or does it inherit the session's?** Until proven otherwise they are treated as the same agent, with attribution (`via`).
- **Two languages:** the backend/frontend contract depends on generating types from OpenAPI (ADR-0001); drift is checked in CI.

## How to resume

1. Read this file, then `CLAUDE.md`, then the current spec.
2. `git status` and `git log --oneline -10` to see the real state.
3. Check `docs/bootstrap-tasks.md` for the next task.
4. When the block is done: rewrite this file.
