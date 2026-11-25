# ADR-0006: Append-only, hash-chained event log

- **Status:** accepted
- **Date:** 2026-11-26

## Context

The owner wants an immutable history of changes and to know who did what (human, which agent). The same log feeds live updates and, later, automation triggers.

## Decision

Every state change writes one row to `events` **in the same transaction** as the change: actor, entity, event type, JSON payload, timestamp, and the hash of the previous event. Database triggers reject `UPDATE` and `DELETE` on `events`. Current-state tables are projections kept in step with the log. A `verify` command recomputes the chain.

Full event sourcing (rebuilding state only from events) was considered and rejected as unnecessary complexity at this scale.

## Consequences

- Audit, "who did this" and the activity feed come from one source.
- The hash chain makes tampering detectable, not impossible; it is not a security boundary against someone with file access.
- The same stream drives SSE and, later, automation triggers.
