# ADR-0001: Python backend, React frontend, one container

- **Status:** accepted
- **Date:** 2026-11-26

## Context

Kairos needs a web API, an MCP server for agents, live updates and a desktop PWA, running locally in Docker on Windows with a small footprint. The owner prefers web technologies (TypeScript, Python, PHP, SQL). Three options were weighed:

- **A. TypeScript end to end.** One language and one contract definition (Zod). Recommended by the assistant.
- **B. Python backend + React frontend.** Strong LLM/MCP ecosystem, two languages.
- **C. Separate services + PostgreSQL.** Rejected: more containers and RAM with no benefit at ~200 active tasks and one user.

## Decision

Option **B**, chosen by the owner:

- Backend: Python, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, SQLite. Tooling: `uv`, Ruff, pyright, pytest, Hypothesis.
- Frontend: React, Vite, TypeScript, TanStack Query, Tailwind, dnd-kit, `vite-plugin-pwa`. Tooling: pnpm, Biome, Vitest, Playwright.
- The built frontend is served as static files by the FastAPI process: **one container**.

## Consequences

- Two toolchains. A single `check` command must run both sides.
- **Contract risk:** Pydantic models are the source of truth. TypeScript types are generated from the OpenAPI schema (`openapi-typescript`) and never edited by hand. CI fails if the generated file is out of date.
- MCP tools reuse the same Pydantic models as the REST API.
- Node is only needed at build time; the runtime image is Python only.
