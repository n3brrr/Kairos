# Stage 1: decomposition and domain approach

**Date:** 2026-11-26 · **Status:** proposed, waiting for the owner's approval · **Size:** small (a short design on top of the closed [Kairos design](2026-11-26-kairos-design.md))

The Kairos design already defines *what* stage 1 builds (§6 to §10, §15). This document only settles *how stage 1 is cut into plans* and the technical decisions of its first slice. It reopens nothing in the design.

## Intent

Reach the stage 1 milestone: the agents use Kairos to track Kairos's own tasks (dogfooding). A precise, governed model is the point of the product, so the rules come first and are tested before any entry point can reach them (ADR-0003).

## Approaches considered

| Approach | Trade-off | Outcome |
|---|---|---|
| **A. By layers** | Gates, permissions and invariants are fully tested before anything exposes them, so little rework. Dogfooding starts only after the UI slice. | **Chosen by the owner.** |
| B. Thin vertical slice first | Reaches dogfooding sooner. The design needs the full hierarchy, dependency and date model from the start, so the domain would be reopened. | Rejected. |

## The slices

Each slice is its own plan (`docs/superpowers/plans/`) and its own pull requests. A slice starts only when the previous one is merged. Their detail is decided when each plan is written.

| # | Slice | Delivers | Needs |
|---|---|---|---|
| 1 | **Pure domain** | Item kinds and hierarchy, statuses, transition table, gates, permission policy, dependencies and derived "blocked", progress, assignment invariants, event types. No I/O. | Stage 0 |
| 2 | **Persistence and history** | SQLite, Alembic, repositories, use cases that apply domain decisions, the hash-chained `events` log with its triggers and `verify`. | 1 |
| 3 | **REST and owner login** | `/api/*` over the use cases, owner password (argon2id) and session cookie, CSRF, attempt limiting, one-time local command that creates the owner account. | 2 |
| 4 | **MCP, agents and tokens** | `/mcp` with the agent token from the `Authorization` header (ADR-0005), token issue and revocation, the agent and orchestrator tools, `.mcp.json`. Includes the ADR-0005 verification of a per-subagent token through an agent file. | 3 |
| 5 | **Minimal UI** | Owner login, simple task list, approval queue, agent and token management, generated API types in use. | 3 (4 for live data) |
| 6 | **Dogfood** | Import `docs/bootstrap-tasks.md` into Kairos; the agents start working from it. | 4 and 5 |

## Slice 1: domain approach

These are my calls (the design leaves them to the builder, §18). The owner may change them.

- **Pure Python, no framework.** `domain/` uses `dataclasses` (frozen) and `enum`, with no Pydantic, SQLAlchemy or FastAPI import. Pydantic stays at the edges (API, MCP). A test fails if `domain/` imports from outside the standard library or itself.
- **Decisions, not mutations.** Domain functions take the current state, the `Actor` and the requested action, and return either an `Allowed` decision carrying the new state and the events to record, or a `Rejected` with a stable reason code and a message. The use cases of slice 2 persist what the domain decided. There are no exceptions for expected rejections.
- **One policy table.** Transitions, who may perform them and which gates apply live in one data structure that mirrors the table in design §6.3. A test derives the expected matrix from that section, so the code and the spec cannot drift silently.
- **Gate override.** Only the owner may skip a gate, and only with a non-empty reason; the decision then carries a `gate_overridden` event (design §6.4).
- **Dependencies.** "Blocks" edges, cycle detection on insert, and `is_blocked` derived from open dependencies. A cancelled dependency counts as resolved and the decision carries a warning (design §6.7).
- **Progress.** A leaf is criteria met over total (100% when done). A container is the unweighted mean of its non-cancelled children; a container with none is 0%. This fixes the formula the design left open (§6.5, §18).
- **Epic status** is derived exactly as in design §6.1.
- **Queue limit.** Up to 3 assigned tasks per agent, configurable per agent; tasks in `in_review` do not count (design §6.8).
- **Tests.** Table-driven tests for the policy, plus property-based tests with Hypothesis for the invariants: no cycles, at most one `in_progress` per agent, at most one active agent per task, and "an agent or the orchestrator can never reach `done`, `cancelled` or a deletion". Hypothesis is added as a development dependency. TDD, red then green, as always.
- **Out of scope for slice 1:** the database, HTTP, tokens, sessions, the UI and the event hashing (slice 2).

## Goals, non-goals, anti-goals

- **Goal:** the rules of §6 exist once, in `domain/`, fully tested.
- **Non-goal:** any entry point or persistence in this slice.
- **Anti-goal:** a rule that only some entry point enforces, or a domain test that only exercises the happy path.

## Left to the builder

Module and type names inside `domain/` (they follow `docs/GLOSSARY.md`), how events are typed, and the exact Hypothesis strategies. Each slice's plan fixes the rest.
