# ADR-0002: SQLite as the only datastore

- **Status:** accepted
- **Date:** 2026-11-26

## Context

"Local database", small footprint, one human user plus a handful of agents, at most ~200 active tasks (plus queued ones). Writes are low volume and mostly sequential.

## Decision

SQLite in WAL mode, accessed through SQLAlchemy 2, with Alembic migrations. Writes use `BEGIN IMMEDIATE` transactions. The database file lives in a **named Docker volume** (`/data`), never in a Windows bind mount, because WAL relies on shared memory that is not reliable across the Windows/WSL file boundary. Backups use SQLite's online backup API and write a copy to a host-mounted folder.

PostgreSQL was rejected: an extra container and RAM for a scale that does not need it.

## Consequences

- No extra service; tests run on in-memory databases.
- Database-level guards back up domain rules (defense in depth): a partial unique index allows one `in_progress` item per agent, and triggers forbid `UPDATE`/`DELETE` on `events`.
- If Kairos ever becomes multi-user or networked, this decision must be revisited.
