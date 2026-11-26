# Kairos

A **precise, governed** task board for one person and their Claude Code agents. It runs in Docker on Windows (`localhost`), is a desktop PWA with a dark theme, and manages its own development. The repo is public: it doubles as a showcase of professional engineering.

## Read this before acting

1. `docs/STATUS.md`: where we are and what comes next. **Rewrite it when you close each block of work.**
2. `docs/superpowers/specs/`: the current design. `docs/adr/`: decisions and their reasons. `docs/GLOSSARY.md`: vocabulary.
3. To propose improvements: `docs/FEATURES.md` (it explains the "review passes").

## How we work (superpowers)

brainstorming → approved spec → writing-plans → TDD (red/green) → verification before claiming anything is done.

- **No product code without an approved spec and a plan.**
- Never claim something works without running the verification command and reading its output.

## Code status

Foundations only: a health endpoint, a PWA skeleton and the tooling. Decided stack (ADR-0001): Python backend (FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, SQLite), React + Vite + TypeScript frontend, one Docker container. **Do not invent commands that are not listed here.**

Commands (Python via `uv`, JavaScript/TypeScript via `pnpm` only):

| Command | From | What it does |
|---|---|---|
| `python tools/check.py` | repo root | **The single `check`**: format, lint, types and tests for backend, tools and frontend, the contract drift check and the frontend build. Runs every step and exits `1` if any fails. |
| `uv run pytest -q` | `backend/` | Backend tests. |
| `uv run ruff check --config pyproject.toml . ../tools` | `backend/` | Python lint (also covers `tools/`). Use `ruff format` to format. |
| `uv run pyright` | `backend/` | Strict type check. |
| `uv run --project backend pytest tools/tests -q` | repo root | Repo tooling tests. |
| `uv run --project backend python tools/gen_api_types.py [--check]` | repo root | Regenerate (or verify) `frontend/src/api/schema.d.ts` from OpenAPI. Never edit that file by hand. |
| `pnpm test` / `lint` / `typecheck` / `build` / `dev` | `frontend/` | Vitest, Biome, `tsc`, production build, dev server (proxies `/api` to `127.0.0.1:8000`). |
| `uv run uvicorn kairos.main:create_app --factory` | `backend/` | Start the backend. |

## Planned repo map (what already exists is marked)

```
CLAUDE.md                ✓  this file
docs/                    ✓  context, status, roadmap, ADRs, specs, plans
.claude/                    agents/ · skills/ · rules/ · settings.json   (stage 0)
.mcp.json                   Kairos connected to itself                    (stage 1)
backend/                    Python: domain/ (pure) · features/ · adapters/
frontend/                   React: features/ (dashboard, board, task, agents)
tools/                      repo tooling: check, type generation, hooks   (stage 0)
Dockerfile · compose.yaml   a single container
.github/                    CI, Dependabot, PR template                   (stage 0)
```

## Golden rules (non-negotiable)

1. **Single door.** The UI, MCP and automations call the same use cases with an `Actor` (human, agent or orchestrator). Gates and permissions live in `domain/`; no entry point can skip them, not even a script.
2. **Agents never approve, cancel or delete.** They can only request; the human decides.
3. **Immutable history.** `events` is append-only: never `UPDATE` or `DELETE` on it.
4. **Contracts.** Pydantic models are the source of truth; TypeScript types are generated from OpenAPI and never edited by hand.
5. **No Anthropic API.** The owner uses a Claude Pro quota: Kairos never calls Claude. Claude Code sessions connect to Kairos over MCP.
6. **Security.** The port listens only on `127.0.0.1`; passwords and tokens are stored only as hashes; no secrets in the repo (`.env` stays out, `.env.example` goes in).
7. **Data.** SQLite lives in a **named** Docker volume, not a bind mount (WAL is not reliable on Windows bind mounts).
8. **One PR, one purpose.** Small, focused changes.
9. **Package managers.** `pnpm` for everything JavaScript/TypeScript (install, run, exec, dlx); never `npm`, `npx`, `yarn` or a `package-lock.json`. `uv` for Python; never `pip install` into the system. A hook enforces this from stage 0.

## Language

- **Chat with the owner: Spanish.** Only there.
- **Everything else: English**: code, identifiers, UI strings, docs (including this file, `STATUS`, `ROADMAP`, specs and plans), ADRs, agent/skill/rule definitions, prompts sent to subagents, commit messages, PRs and the README.
- UI strings live in a message catalog (no hardcoded text in components) so another language can be added later.
- `docs/GLOSSARY.md` has a Spanish column only to map the owner's chat vocabulary to the English terms.

## Git flow (overrides the `git-commit-push` skill; see ADR-0004)

The skill assumes one person and a long-lived `dev` branch. Several agents work in parallel here, so:

- **Trunk-based.** `main` is always stable. Never commit or push directly to `main`. **There is no `dev`.**
- **One short-lived branch per task**, created from `origin/main`: `<type>/<ID>-<slug>`. Example: `feat/KAI-12-approval-queue`. Before Kairos exists the ID is `BOOT-<n>` (see `docs/bootstrap-tasks.md`). Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `build`, `ci`.
- **One worktree per agent**, never a shared folder: `git worktree add ../Kairos-wt/<ID> -b <branch> origin/main`. The `Kairos-wt/` folder is a sibling of the repo, outside it.
- **Commits:** Conventional Commits in English, imperative, ≤72 characters, atomic. `git add <file>` by name, never `git add .`. Never `--no-verify`.
- **Keep the branch current** with `git merge origin/main`; do not rebase a published branch.
- **PR to `main`:** conventional title with the ID (`feat(tasks): add approval queue (KAI-12)`), English body with *What changed / Why / How it was tested* and a link to the task. Before opening it, `check` must pass on the final state.
- **Merge: the owner only**, by **squash**, and the branch is deleted. No agent merges (same rule as with tasks).
- **`main` ruleset** (the owner imports it on the web): PR required, `check` status required and branch up to date, **linear history**, no force-push or deletion, 0 approvals, no bypass. Dependabot targets `main`.
- **The rest of the skill still applies:** pre-flight repo review, warn before adding CI or bots, no force-push, no rewriting published history, no secrets, no mixing purposes in a PR.

## Keeping the docs alive

- `docs/STATUS.md`: rewritten when closing each block (done, next, blockers).
- `docs/ROADMAP.md`: updated when stages are completed or moved.
- `docs/adr/`: a new decision is a new ADR. Accepted ADRs are not edited: a later one *supersedes* them.
- `docs/FEATURES.md`: new ideas are written there; they are not built without approval.
- If the code changes something a doc describes, the doc changes in the same PR.
