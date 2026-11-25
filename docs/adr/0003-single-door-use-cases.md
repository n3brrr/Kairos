# ADR-0003: Single door: every entry point goes through the same use cases

- **Status:** accepted
- **Date:** 2026-11-26

## Context

Kairos is reached by three kinds of callers: the web UI, agents over MCP, and (later) automations. The central promise is that agents cannot bypass gates or permissions. If rules lived in the UI or in one adapter, another entry point could skip them.

## Decision

All state changes are **application use cases** that take an `Actor` (human, agent, orchestrator or system) and return a result or a typed rejection. Gates, transition rules and the permission policy live in a pure `domain/` package with no I/O. REST routes, MCP tools and the automation engine are thin adapters that authenticate, build the `Actor`, and call a use case. Nothing writes to the database around the use cases.

## Consequences

- Rules are tested once, with fast unit and property-based tests, without HTTP or a database.
- Adding an entry point cannot weaken the rules.
- A little ceremony per feature: use case + adapter + repository.
- Database constraints (ADR-0002) are a second line of defense, not the first.
