# ADR-0004: Trunk-based git flow (supersedes the `dev` → `main` flow of the git-commit-push skill)

- **Status:** accepted
- **Date:** 2026-11-26

## Context

The owner's `git-commit-push` skill uses a long-lived `dev` branch and a merge-commit pull request into `main`. That fits one person working in one folder. Kairos is built by several Claude Code agents in parallel. A shared `dev` branch would make all of them push to the same ref and collide, and it hides which task produced which change.

## Decision

- `main` is always releasable and only changes through pull requests. There is no `dev`.
- One short-lived branch per task, named `<type>/<ID>-<slug>`, created from `origin/main`, in its own git worktree per agent.
- Pull requests are **squash-merged by the owner**; the branch is deleted afterwards. Agents never merge.
- Conventional Commits in English; the squash title carries the task ID.
- The `main` ruleset requires a PR, the `check` status (up to date), linear history, and forbids force-push and deletion; 0 required approvals (single owner), no bypass.

Everything else in the skill still applies (pre-flight repo review, no force-push, no history rewriting on published branches, no secrets, one purpose per PR).

## Consequences

- Linear history: each commit on `main` maps to one Kairos task.
- Parallel agents do not interfere with each other.
- Rules live in `CLAUDE.md`, which takes precedence over the skill.
