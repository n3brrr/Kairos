# Kairos — Design Document

**Date:** 2026-11-26 · **Status:** closed after review, open points resolved (§17.1); the owner can still review it in the BOOT-001 PR · **Size:** project (full design)

Convention: what the owner decided is written as decided. What I (Claude) decided without agreeing it with the owner is marked **(my call)** and collected in §17, so it can be reviewed and changed.

## 1. Intent and why

Kairos (from the Greek *kairós*, "the opportune moment") is a task board for **one person and their Claude Code agents**. It exists because Trello lacks two things:

1. With many open tasks (up to ~200 active, plus queued projects and tasks) there is no way to categorize them or get an overview.
2. You cannot work with an AI agent while keeping real control over what it does.

What sets it apart: (a) a precise data model (statuses with transitions, types with required fields, dependencies, acceptance criteria with evidence, hierarchy, dates with semantics, immutable history) and (b) **strict agent control**: identity, bounded scope, one task in progress at a time, and human approval to close, like a PR.

A secondary, explicit goal: the repo is **public** and must show recruiters professional engineering and LLM integration.

## 2. Actors

- **Owner (human):** the single owner. Has every permission.
- **Agents:** Claude Code sessions with their own identity: name, specialty (for example "bugs"), allowed task types and projects, token. Several can work at once in the same project.
- **Orchestrator:** an agent with an extended role that decides who does what. It does not approve.
- **System (stage 3):** automations act as an actor with bounded permissions.

## 3. Goals, non-goals and anti-goals

**Goals**
- A precise model and agent control as described in §1.
- A dashboard as the landing screen, to see the whole picture at a glance (§10).
- Kairos manages its own development as soon as it has the minimum (stage 1).
- Small footprint: little RAM and CPU, without sacrificing features.
- A repo optimized for working with Claude Code and several agents (§12).
- Visible professional quality: tests, CI, ADRs, documentation.

**Non-goals (for now)**
- Several human users; mobile access; offline editing or sync between devices.
- Any UI language other than English (strings live in a message catalog so another can be added later).
- Exposure to the internet or deployment on the home server.
- Calling the Anthropic API (the owner uses a Claude Pro quota).
- Automatic agent execution (arrives with the *runner*, stage 4).

**Anti-goals (a failure even if it "works")**
- A cosmetic lock: rules that live only in the UI and that an agent can skip through another entry point.
- A repo that only works on the happy path or without tests.
- Complexity beyond the scale (microservices, PostgreSQL, Kubernetes).
- Depending on the paid API.

## 4. Constraints

- Windows 11 with Docker Desktop; everything on `localhost`. Python 3.13, Node 24, pnpm and `gh` are already installed; **`uv` is not installed**.
- Desktop UI, **English**, dark mode. The owner first asked for a Spanish UI and later instructed that everything except the chat with them is in English; the later instruction wins. **(my call: keep strings in a message catalog so Spanish can be added back cheaply.)**
- Local database (SQLite, ADR-0002), reachable by agents through Kairos, not directly.
- Web technologies: TypeScript, Python, SQL.
- Public GitHub repo, MIT license, `main` unprotected until the owner imports the ruleset.

## 5. Approaches considered

Detail and consequences in ADR-0001.

| Approach | Outcome |
|---|---|
| A. TypeScript end to end | Recommended by me: one language and one contract definition. **Not chosen.** |
| **B. Python backend + React frontend, one container** | **Chosen by the owner.** Better LLM/MCP ecosystem and uses Python. Cost: two languages; mitigated by generating the TS types from OpenAPI (Pydantic is the source) and checking drift in CI. |
| C. Separate services + PostgreSQL | Rejected: more containers and RAM with no benefit at this scale. |
| PHP / Laravel | Rejected: MCP and real time fit worse. |

## 6. Domain model

### 6.1 Hierarchy and per-class behavior
Project › Epic › Task › Subtask. A task may hang directly from a project, without an epic. How they map to tables is left to the builder (recommendation: one `items` table with `kind` and `parent_id`). Each class behaves differently **(my call)**:

- **Project:** its own lifecycle (active, queued, paused, archived) and an **area** attribute (editable list, for example Personal, Development). No criteria or review.
- **Epic:** groups tasks. No assignment, criteria or review. Its status is **derived** from its children: not started, in progress, or complete when all its tasks are done or cancelled.
- **Task:** the assignable unit. Uses the seven statuses, criteria and review. **It is the only class that counts** toward "one in progress per agent".
- **Subtask:** a step of a task, with a simple status (pending or done) and no assignment of its own: whoever carries the task carries it. A task cannot move to `in_review` with pending subtasks.

### 6.2 Fields and types
**Base fields** of a task: title, description, type, priority (P0–P3), free labels, parent (project or epic), dates (§6.7), dependencies, acceptance criteria, assignee and delivery summary. **Categorizing** a task means combining project (with its area), type, labels and priority **(my call)**.

A **type** (bug, feature, chore, research, personal…) defines **which of the base fields are required** and a template of acceptance criteria. Types are editable data, not code. **Decided with the owner: a fixed field list in stage 1.** Custom fields per type remain a future idea (`IDEA-15` in `FEATURES.md`).

### 6.3 Stored statuses and transitions

`proposed → backlog → ready → in_progress → in_review → done`, plus `cancelled`. In the UI: Proposal, Backlog, Ready, In progress, In review, Done, Cancelled.

**Blocked is not a stored status:** it is derived. A task with open dependencies is shown as blocked and cannot move to `in_progress`.

| Action | Owner | Orchestrator | Agent |
|---|---|---|---|
| Create (always as `proposed` if an agent creates it) | yes | yes | yes, only as a proposal |
| `proposed → backlog` (triage) | yes | yes | no |
| `backlog → ready` | yes | yes | no |
| Assign to an agent (assigning is reserving) | yes | yes | no |
| `ready → in_progress` | yes | no | yes, only if assigned to it |
| `in_progress → in_review` | yes | no | yes, if it passes the gates |
| `in_review → done` (approve) | yes | **no** | **no** |
| Return a delivery with a comment (`in_review → ready`, **keeps the assignment**) | yes | no | no |
| Release a task (`in_progress → ready`, **removes the assignment**) | yes | yes | yes, with a reason |
| Move backwards (for example `ready → backlog`, dragging on the board) | yes | no | no |
| Discard a proposal (`proposed → cancelled`) | yes | **no** | no |
| Reopen `done` or `cancelled` (to `backlog` or `ready`, with a reason) | yes | no | no |
| Cancel | yes | **no** | only requests (§6.6) |
| Delete | yes | **no** | **no** |
| Change permissions, tokens, automations | yes | **no** | **no** |

The owner can also work on a task at the same time as an agent, but there is **never more than one active agent** on the same task.

### 6.4 Gates (automatic)
To move to `in_review`: required fields of the type complete, **every criterion with evidence**, no open dependencies and a non-empty delivery summary. If it fails, the system rejects the action and says why.
To move to `in_progress`: the task is assigned to the actor, has no open dependencies and the agent has no other task in progress.
To move to `ready`: at least **one acceptance criterion**, so "every criterion has evidence" is never vacuous **(my call)**.

**Gates always bind agents and the orchestrator.** The owner can **override** them by giving a reason, which is recorded in the history as `gate_overridden` **(my call)**. The one exception is "one `in_progress` task per agent": it is an invariant (§6.8, also a database constraint, ADR-0002), so nobody can override it, the owner included **(my call, decided while building slice 1)**.

### 6.5 Criteria, evidence and progress
Every task has acceptance criteria; each criterion is met by attaching **evidence** (text, link or command output). **Progress** of a leaf = criteria met / total (100% if done). Containers average their children (exact formula left to the plan).

**Who writes the criteria (my call).** The owner or the orchestrator define them, or they come from the type's template. An agent may *draft them inside a proposal*; once promoted, it **cannot add, edit or delete criteria: it can only attach evidence**. On its own task, an agent may change only comments, evidence, delivery summary and working notes; not title, type, priority, dates, parent or dependencies. Evidence enters only by attaching it to a criterion, never through the criteria field, so it keeps its author and its history event. A task's type cannot change while it is assigned, because its assignee was chosen for that type **(my call, decided while building slice 1)**.

### 6.6 Approval requests
Like a PR: an agent that wants to cancel or close a task creates a **request** with a description and a reason; it stays pending until the owner approves or rejects it (with a note). Moving to `in_review` implicitly creates the approval request for the delivery.

### 6.7 Dependencies, dates and recurrence
"Blocks" dependencies, no cycles. A **cancelled dependency counts as resolved** and the owner gets a warning **(my call)**. Dates with semantics: start, due date and recurrence (the model stores it from stage 1; the engine that generates instances arrives in stage 3).

### 6.8 Assignment
An agent does not self-assign: it starts only what the orchestrator or the owner assigned. **There is no separate "reservation":** assigning already reserves. Invariants the domain enforces **on the orchestrator too**: one `in_progress` task per agent, one active agent per task, task type and project within the agent's scope, no open dependencies.

**Queue.** Decided with the owner: an agent is **not limited to a single assigned task**. It may have a queue of up to 3 assigned tasks (limit configurable per agent **(my call)**) but **only one `in_progress`**. Tasks in `in_review`, waiting for the owner's approval, do not count toward the limit.

**Subagents on large tasks.** The owner asked to be able to use "a couple of subagents or more" on large tasks. **My interpretation:** an agent may lean on subagents of its own session. Kairos treats them as the **same agent** (no extra permissions, and there is still a single active agent per task) and records in the history which subagent did what, as attribution only. Whether each subagent has its own token depends on the spike (ADR-0005).

### 6.9 Visibility
- **Agent:** sees its assigned tasks in full, plus the minimum context to work: parent project or epic (title and summary) and, for what blocks it, id, title and status. It does not see the content of other agents' tasks.
- **Orchestrator:** sees all tasks (it needs to distribute them) and the agents' profiles, never the tokens.
- **Owner:** sees everything.

### 6.10 History
Immutable, append-only, hash-chained event log (ADR-0006). Every event stores who (owner, which agent) and why.

## 7. Architecture

One container with one FastAPI process that exposes:

- **REST** `/api/*` for the UI, with the owner's session.
- **MCP** `/mcp` (Streamable HTTP) for agents, with a per-agent token (ADR-0005).
- **SSE** for live UI updates.
- The React SPA as static files.

Backend layers (ADR-0003): `domain/` (pure: statuses, gates, permissions), `features/<x>/` (use cases, repository, routes, MCP tools and tests together) and `adapters/`. Contracts are Pydantic models; the frontend gets TypeScript types generated from OpenAPI (ADR-0001). Defense in depth: a partial unique index "one `in_progress` per agent" and triggers that forbid modifying `events` (ADR-0002).

## 8. Agent interface (MCP)

Planned tools (exact names left to the plan):
- **Agent:** get its context and tasks, view a task, start it, release it with a reason, comment, update permitted fields, record evidence on a criterion, submit for review with a summary, propose a task, request cancellation.
- **Orchestrator (adds):** list all tasks and agents, assign, triage proposals, split an epic into proposals.

The spike (ADR-0005) validates authentication before this design is fixed.

## 9. Security

- The port listens only on `127.0.0.1`; `Origin` and `Host` are validated (DNS-rebinding protection).
- **Owner:** password with argon2id, `HttpOnly` and `SameSite=Strict` session cookie, CSRF protection and attempt limiting. Passkeys as a later hardening **(my call)**. The initial account is created with a one-time local command **(my call)**.
- **Agents:** 256-bit random token, stored only as a hash, scoped and revocable, with `last_used_at`. Shown once at creation. An agent token is useless on the owner's endpoints, and vice versa.
- No secrets in the repo; the agent token arrives through an environment variable.
- Non-root container with a read-only filesystem except the data volume.

## 10. Dashboard and views

Landing screen: a dashboard with the main metrics, the active projects and the pending ones. At a glance it must answer:

1. **Waiting for your approval:** deliveries and requests pending. It goes first because it is what stalls the agents.
2. **Active projects** with progress %, and separately the queued projects.
3. **Blocked and overdue.**
4. **What each agent is doing now**, live.
5. **Recent activity**, taken from the history.

**Kanban board**, adapted: columns by status, filterable by project, type, subtask status, agent and progress %. In stage 1 a **simple task list** exists as the minimal UI for dogfooding **(my call)**; calendar and timeline stay out until requested.

**Look:** "mythological but simple", dark mode. Designed with mockups in stage 2; for now it only reserves that colors and typography are replaceable theme tokens.

## 11. PWA and real time

An installable desktop PWA (`localhost` counts as a secure context, no HTTPS): manifest and service worker for the shell. No offline data mode (non-goal). Changes made by agents appear on screen through SSE, without reloading.

## 12. Repo optimized for Claude Code

- A short root `CLAUDE.md` (map, golden rules, git flow) and a per-module `CLAUDE.md` when needed; `.claude/rules/` scoped by path.
- Structure by feature and small files: an agent works in a single folder without loading the rest.
- `.claude/agents/` (orchestrator, backend, frontend, bugs, reviewer), `.claude/skills/` with repeatable procedures (new migration, new MCP tool) and hooks for what must never break (formatting, blocking destructive commands, a reminder to update `docs/STATUS.md`).
- A single `check` command (lint, types, backend and frontend tests) as the verification loop.
- One git worktree per agent (ADR-0004).
- `docs/` as the project's memory: status, roadmap, glossary, ideas, ADRs and bootstrap tasks.
- Kairos connects to itself through `.mcp.json` from stage 1.

## 13. Automations (stage 3; the event model prepares them from stage 1)

- Workflows defined as **versioned, validated JSON** (Pydantic): trigger (event or cron) → conditions → actions (create or move a task, notify, webhook).
- **Three editing modes over the same JSON:** visual builder, declarative file and API (agents can design them).
- Scheduling with an in-process scheduler; reminders and notifications; outgoing webhooks.
- **Agent execution:** it cannot be launched from inside the container because Claude Code lives on Windows. A *runner* on the host (stage 4) is needed, with limits and prior approval.

## 14. Quality and delivery

- Test pyramid: unit and property-based tests (Hypothesis) on `domain/`, integration with in-memory SQLite, MCP contract tests with a real client, and e2e with Playwright.
- Red/green TDD for every feature.
- CI: a `check` job in GitHub Actions that runs the same local `check`, plus a generated-types drift check, an image build and Dependabot (`uv`, `npm`, `docker`, `github-actions`), each in its own PR.
- Multi-stage Docker image, non-root user, healthcheck.

## 15. Stages

Summary; the live status is in [`docs/ROADMAP.md`](../../ROADMAP.md).

0. **Foundations and spike:** tooling, structure, `check`, Docker, `.claude/`, CI, MCP spike.
1. **"Dogfood-ready" core:** domain with the **full hierarchy, dependency and date model** (gates and agent context need it), persistence with history, REST and MCP with tokens, orchestrator, minimal UI with a simple list and the approval queue. *From here on, agents use Kairos to build Kairos.*
2. **Board and dashboard:** filterable kanban, hierarchy, dependency and date views, dashboard, SSE, look.
3. **Automations:** engine, cron, notifications, webhooks, visual builder.
4. **Execution and hardening:** runner, passkeys, backups, portfolio README.

## 16. Risks

- **MCP authentication on Windows** (ADR-0005): ruled out or confirmed by the spike, before stage 1 is fixed.
- **Per-subagent token:** if it is not possible, "one agent" means "one Claude Code session" and the role design adapts.
- **Contract drift between two languages:** type generation and a CI check.
- **SQLite on Docker Desktop:** only with a named volume (ADR-0002).
- **Claude Pro quota:** an orchestrator running in a loop would burn it; it runs on demand.

## 17. My calls (not agreed; the owner may change them)

- Language: chat with the owner in Spanish; everything else, UI included, in English; strings in a message catalog (§4).
- Hash-chained history (ADR-0006) and a `verify` command.
- pyright in strict mode and Ruff; Biome on the frontend; pnpm.
- Owner authentication: password + session in the MVP; passkeys later. Initial account created by a local command.
- "Blocked" as a derived status, not a stored one.
- An agent does not self-assign; the orchestrator may triage (promote) proposals but **not** discard them: discarding is the owner's.
- Agent proposals: any agent may create them within its scope.
- A single `main` + short branches with squash, and a worktree per agent (ADR-0004).
- The orchestrator runs on demand, not in a loop.
- Behavior per item class, base fields and categorization by project + area + type + labels + priority (§6.1, §6.2).
- An agent only attaches evidence; it does not edit criteria after triage; a task needs at least one criterion to move to `ready` (§6.4, §6.5).
- Returning a delivery moves it to `ready` keeping the assignment; releasing a task removes the assignment (§6.3).
- Discarding a proposal and reopening closed tasks are the owner's only; the owner may override gates with a recorded reason.
- A cancelled dependency counts as resolved, with a warning.
- No separate "reservation": assigning already reserves; the queue limit of 3 is configurable per agent.
- Stage 1 includes the full hierarchy model and a simple list; kanban in stage 2.

### 17.1 Resolved with the owner after the spec review

1. **Tasks per agent** (§6.8): not just one. A short queue of assigned tasks, a single one in progress, and supporting subagents on large tasks (my reading of the subagent request; see §6.8).
2. **Custom fields per type** (§6.2): a fixed list in stage 1; custom fields later.

No spec questions remain open.

## 18. Left to the builder

Exact dependency versions; synchronous or asynchronous ORM (recommendation: synchronous for SQLite, with asynchronous SSE over an in-memory event bus); table, column and MCP tool names; the exact container progress formula; the cross-platform `check` runner (the plan fixes it: a stdlib Python script); the exact folder structure inside each feature; Tailwind configuration and theme tokens.
