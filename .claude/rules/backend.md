---
paths:
  - "backend/**"
---

# Backend conventions

- Python 3.13, managed with `uv`. Never `pip install` into the system.
- Layout: `domain/` is pure (no I/O, no framework imports); `features/` holds one folder per feature (API, use cases); `adapters/` holds the database and other I/O.
- Gates and permissions live in `domain/`, never in route handlers. Every entry point calls the same use case with an `Actor`.
- Pydantic v2 models are the contract. Changing one means regenerating the frontend types (`uv run --project backend python tools/gen_api_types.py`).
- `events` is append-only: never `UPDATE` or `DELETE` it.
- Passwords and tokens are stored only as hashes. No secrets in the repo.
- Ruff (format + lint) and pyright strict must be clean. Tests live in `backend/tests/`.
- Write the failing test first.
