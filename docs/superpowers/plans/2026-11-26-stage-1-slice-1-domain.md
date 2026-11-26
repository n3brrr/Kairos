# Stage 1, Slice 1: Pure Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `backend/src/kairos/domain/`: the item model, statuses, gates, permission policy, dependencies, progress, assignment, approval requests and event types of the Kairos design, as pure Python that returns decisions, fully tested.

**Architecture:** Domain functions take the current state, an `Actor` and the requested action, and return `Allowed` (new state plus the events to record) or `Rejected` (stable code plus message). No I/O, no framework, no exceptions for expected rejections. Slice 2 persists what the domain decides.

**Tech Stack:** Python 3.13 (standard library only inside `domain/`), pytest, Hypothesis (new dev dependency), Ruff, pyright strict. All commands from `backend/` with `uv`.

**Spec:** [`../specs/2026-11-26-kairos-design.md`](../specs/2026-11-26-kairos-design.md) (§6, §8, §14) and [`../specs/2026-11-26-stage-1-decomposition-design.md`](../specs/2026-11-26-stage-1-decomposition-design.md) (slice 1). ADR-0003, ADR-0006. Vocabulary: `docs/GLOSSARY.md`.

## Global Constraints

- `domain/` imports only the standard library and itself. A test enforces it (Task 1). No Pydantic, SQLAlchemy, FastAPI, clock or randomness: ids, timestamps and `date` values come from the caller.
- Python 3.13; pyright **strict** and Ruff must be clean on `src` and `tests`. Frozen dataclasses, `enum.StrEnum`, `tuple`/`frozenset` for collections.
- Names follow `docs/GLOSSARY.md`. Everything in the repo is English.
- TDD, red then green: every task starts with a test that was watched failing. Whole suite (`python tools/check.py`) green before each PR.
- Git: three stacked branches from `origin/main`, one execution worktree `../Kairos-wt/BOOT-011`; Conventional Commits; `git add <file>` by name; never `--no-verify`; the owner squash-merges. After a PR is merged, `git merge origin/main` into the next branch and `gh pr edit <n> --base main`.
- No Anthropic API, no secrets. Out of scope: database, HTTP, tokens, sessions, UI, event hashing.

## My calls (the design leaves them to the builder; record any change in the ledger)

- Assignment is allowed only on `READY` tasks and is kept in `READY`, `IN_PROGRESS`, `IN_REVIEW` and `DONE` (record of who delivered); it is cleared when a task goes to `PROPOSED`, `BACKLOG` or `CANCELLED`, on release (`IN_PROGRESS → READY`) and on reopen. Returning a delivery (`IN_REVIEW → READY`) keeps it.
- The queue limit counts the agent's `READY` and `IN_PROGRESS` tasks only (`IN_REVIEW` does not count, as in §6.8).
- "No open dependencies" is checked when a task starts and when it is submitted, not when it is assigned.
- The owner creates tasks as `BACKLOG`; agents and the orchestrator create them as `PROPOSED`, inside their scope.
- The `SYSTEM` actor is rejected for everything until stage 3.
- A task has no criteria after creation unless the creator drafts them; "at least one criterion" is enforced at `READY` and again at `IN_REVIEW`.
- An epic whose children are all cancelled is `COMPLETE` (§6.1); its progress is 0% (no non-cancelled children, per the slice 1 design).

## Review Focus

1. An agent or the orchestrator can never reach `DONE`, `CANCELLED` or any backward move, for every (source, target) pair, even with a `reason` or `override_reason` supplied. Tasks 5 and 9.
2. Dependencies: a self-dependency, a two-step cycle (A→B then B→A) and a longer cycle are all rejected; a `CANCELLED` blocker counts as resolved and returns a warning; a missing blocker id is rejected. Task 3 and 7.
3. Blank text: `"   "` counts as empty for delivery summary, evidence content, reasons, comments and override reasons. Tasks 4, 5, 7 and 8.
4. A task with zero criteria must never pass the `IN_REVIEW` gate (the "every criterion has evidence" rule must not be vacuously true). Task 4.
5. An agent whose queue is full of `IN_REVIEW` tasks can still take new ones; one with a full `READY` and `IN_PROGRESS` queue cannot; a task assigned to agent X is never `IN_PROGRESS` for agent Y. Tasks 6 and 9.

## File structure

```
backend/src/kairos/domain/   actor.py status.py model.py decision.py events.py graph.py
                             progress.py gates.py policy.py assignment.py changes.py
                             approval.py visibility.py
backend/tests/domain/        one test file per module, plus test_domain_purity.py and
                             test_domain_properties.py (basenames must be unique across tests/)
```

---

## PR A (branch `feat/BOOT-011-domain-model`): Tasks 1 to 4

### Task 1: Vocabulary (BOOT-011)

**Files:**
- Create: `domain/actor.py`, `domain/status.py`, `domain/model.py`, `domain/decision.py`, `domain/events.py`; tests `tests/domain/test_domain_purity.py`, `test_status.py`, `test_model.py`
- Modify: `backend/pyproject.toml` (add `hypothesis` to the `dev` group with `uv add --project backend --dev hypothesis`; commit `uv.lock`)

**Interfaces (produces; every later task uses these exact names):**
- `actor.py`: `ActorKind(StrEnum)`: `OWNER, AGENT, ORCHESTRATOR, SYSTEM`. `Actor(kind: ActorKind, id: str, via: str | None = None)` frozen. `AgentProfile(id: str, kind: ActorKind, allowed_task_types: frozenset[str], allowed_project_ids: frozenset[str], queue_limit: int = 3)` frozen; `kind` is `AGENT` or `ORCHESTRATOR`.
- `status.py`: `Status(StrEnum)`: `PROPOSED, BACKLOG, READY, IN_PROGRESS, IN_REVIEW, DONE, CANCELLED`. `ORDER: tuple[Status, ...]` (the first six in that order). `CLOSED = frozenset({DONE, CANCELLED})`. `SubtaskStatus(StrEnum)`: `PENDING, DONE`. `EpicStatus(StrEnum)`: `NOT_STARTED, IN_PROGRESS, COMPLETE`. `ProjectStatus(StrEnum)`: `ACTIVE, QUEUED, PAUSED, ARCHIVED`.
- `model.py`: `ItemKind(StrEnum)`: `PROJECT, EPIC, TASK, SUBTASK`; `can_parent(parent: ItemKind | None, child: ItemKind) -> bool` (project: no parent; epic: project; task: project or epic; subtask: task). `Priority(StrEnum)`: `P0..P3`. `EvidenceKind(StrEnum)`: `TEXT, LINK, COMMAND_OUTPUT`. `Evidence(kind: EvidenceKind, content: str, added_by: str)`. `Criterion(id: str, text: str, evidence: tuple[Evidence, ...] = ())`. `TaskType(name: str, required_fields: frozenset[str], criteria_template: tuple[str, ...] = ())`; `REQUIRED_FIELD_NAMES = frozenset({"description", "priority", "labels", "start_date", "due_date"})`. `Task(id, title, type, project_id, created_by, parent_id=None, status=Status.PROPOSED, priority=Priority.P2, description="", labels=(), start_date=None, due_date=None, recurrence=None, criteria=(), subtasks=(), blocked_by=frozenset(), assignee=None, delivery_summary="", working_notes="")` frozen (`labels: tuple[str, ...]`, dates `datetime.date | None`, `subtasks: tuple[SubtaskStatus, ...]`, `blocked_by: frozenset[str]` = ids of tasks that block this one). `RequestKind(StrEnum)`: `DELIVERY, CANCELLATION`; `RequestState(StrEnum)`: `PENDING, APPROVED, REJECTED`; `ApprovalRequest(task_id: str, kind: RequestKind, requested_by: str, reason: str, state: RequestState = PENDING, note: str | None = None)` frozen. `is_blank(text: str | None) -> bool` (None or whitespace only).
- `events.py`: `EventType(StrEnum)`: `ITEM_CREATED, STATUS_CHANGED, ASSIGNED, UNASSIGNED, GATE_OVERRIDDEN, FIELDS_UPDATED, EVIDENCE_ATTACHED, COMMENT_ADDED, APPROVAL_REQUESTED, APPROVAL_RESOLVED, DEPENDENCY_ADDED, DEPENDENCY_REMOVED`. `Event(type: EventType, entity_id: str, actor: Actor, payload: Mapping[str, object], reason: str | None = None)` frozen (the actor carries `via`).
- `decision.py`: `RejectionCode(StrEnum)`: `NOT_PERMITTED, INVALID_TRANSITION, GATE_FAILED, REASON_REQUIRED, ALREADY_ASSIGNED, OUT_OF_SCOPE, QUEUE_FULL, NOT_ASSIGNED, WRONG_STATUS, DEPENDENCY_CYCLE, UNKNOWN_DEPENDENCY, FIELD_NOT_ALLOWED, UNKNOWN_CRITERION, EMPTY_TEXT, REQUEST_NOT_PENDING, DUPLICATE_REQUEST`. `GateCode(StrEnum)`: `NO_CRITERIA, OPEN_DEPENDENCIES, NOT_ASSIGNED_TO_ACTOR, AGENT_BUSY, MISSING_REQUIRED_FIELDS, CRITERIA_WITHOUT_EVIDENCE, PENDING_SUBTASKS, EMPTY_DELIVERY_SUMMARY`. `GateFailure(code: GateCode, message: str)`. `Rejected(code: RejectionCode, message: str, gates: tuple[GateFailure, ...] = ())`. `Allowed(task: Task, events: tuple[Event, ...], warnings: tuple[str, ...] = (), request: ApprovalRequest | None = None)`. `Decision = Allowed | Rejected` (a `type` alias).

- [ ] **Step 1: Write the failing tests.** `test_domain_purity.py::test_domain_imports_only_stdlib_and_itself` walks `src/kairos/domain/*.py` with `ast` and asserts every import is in `sys.stdlib_module_names` or starts with `kairos.domain` / is relative. `test_status.py`: `test_order_is_the_lifecycle` (`ORDER == (PROPOSED, BACKLOG, READY, IN_PROGRESS, IN_REVIEW, DONE)`) and `test_closed_statuses`. `test_model.py`: `test_can_parent_matrix` (parametrized over every (parent, child) pair against the hierarchy in design §6.1), `test_is_blank` (`None`, `""`, `"  \n"` blank; `"x"` not), `test_task_defaults_to_proposed_and_unassigned`.
- [ ] **Step 2: Run to verify they fail.** `uv run pytest tests/domain -q` from `backend/`. Expected: FAIL (modules missing).
- [ ] **Step 3: Implement** the five modules with the signatures above, and add Hypothesis.
- [ ] **Step 4: Run to verify.** `uv run pytest -q`, `uv run ruff check --config pyproject.toml . ../tools`, `uv run pyright`. Expected: all pass, no findings.
- [ ] **Step 5: Commit.** `git add backend/src/kairos/domain backend/tests/domain backend/pyproject.toml backend/uv.lock`; `feat(domain): add actor, status, item model, decision and event vocabulary (BOOT-011)`.

### Task 2: Dependencies, derived state and progress (BOOT-011)

**Files:** Create `domain/graph.py`, `domain/progress.py`; tests `tests/domain/test_graph.py`, `test_progress.py`.

**Interfaces:**
- Consumes: `Task`, `Status`, `CLOSED`, `EpicStatus`, `Criterion`.
- Produces in `graph.py`: `would_create_cycle(blocked_by: Mapping[str, frozenset[str]], blocker_id: str, blocked_id: str) -> bool` (true for self-edges and for any path from `blocked_id` back to `blocker_id`); `open_blockers(task: Task, statuses: Mapping[str, Status]) -> frozenset[str]` (blockers not in `{DONE, CANCELLED}`; an id missing from `statuses` counts as open); `cancelled_blockers(task, statuses) -> frozenset[str]`; `is_blocked(task, statuses) -> bool`.
- Produces in `progress.py`: `ChildProgress(status: Status, progress: float)` frozen; `task_progress(task: Task) -> float` (`1.0` if `DONE`; else criteria with at least one evidence over total, `0.0` with no criteria); `container_progress(children: Sequence[ChildProgress]) -> float` (mean over non-`CANCELLED` children, `0.0` if none); `epic_status(child_statuses: Sequence[Status]) -> EpicStatus` (children non-empty and all closed: `COMPLETE`; any `IN_PROGRESS`, `IN_REVIEW` or `DONE`: `IN_PROGRESS`; otherwise `NOT_STARTED`).

- [ ] **Step 1: Write the failing tests.** Graph: `test_self_dependency_is_a_cycle`, `test_two_step_cycle`, `test_long_cycle`, `test_diamond_is_not_a_cycle`, `test_done_and_cancelled_blockers_are_resolved`, `test_missing_blocker_counts_as_open`, `test_cancelled_blockers_are_listed`. Progress: `test_progress_of_a_done_task_is_one`, `test_progress_is_criteria_with_evidence_over_total`, `test_task_without_criteria_has_zero_progress`, `test_container_ignores_cancelled_children`, `test_container_without_children_is_zero`, `test_epic_status_table` (parametrized: empty, all backlog, one in progress, one in review, all done, done plus cancelled, all cancelled).
- [ ] **Step 2: Run to verify they fail.** `uv run pytest tests/domain/test_graph.py tests/domain/test_progress.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** both modules; cycle detection is an iterative DFS over `blocked_by` (edges point from a task to its blockers), no recursion.
- [ ] **Step 4: Run to verify.** `uv run pytest tests/domain -q`. Expected: pass.
- [ ] **Step 5: Commit.** `feat(domain): add dependency graph, derived blocked state and progress (BOOT-011)`.

### Task 3: Gates (BOOT-011)

**Files:** Create `domain/gates.py`; test `tests/domain/test_gates.py`.

**Interfaces:**
- Consumes: `Task`, `TaskType`, `REQUIRED_FIELD_NAMES`, `is_blank`, `Actor`, `ActorKind`, `GateFailure`, `GateCode`, `Status`.
- Produces: `GateContext(task_type: TaskType, open_blockers: frozenset[str], other_in_progress: frozenset[str])` frozen (`other_in_progress` = ids of the acting agent's *other* `IN_PROGRESS` tasks; the use case computes both sets). `check_gates(task: Task, target: Status, actor: Actor, ctx: GateContext) -> tuple[GateFailure, ...]` returning every failure, empty when the gates hold. Targets without gates return `()`.
  - `READY`: at least one criterion (`NO_CRITERIA`).
  - `IN_PROGRESS`: no open blockers (`OPEN_DEPENDENCIES`); and, only when `actor.kind` is `AGENT`: `task.assignee == actor.id` (`NOT_ASSIGNED_TO_ACTOR`) and `other_in_progress` empty (`AGENT_BUSY`).
  - `IN_REVIEW`: every field named in `ctx.task_type.required_fields` is non-empty on the task (`MISSING_REQUIRED_FIELDS`); at least one criterion and every criterion has evidence (`CRITERIA_WITHOUT_EVIDENCE`, never vacuous); no `PENDING` subtask (`PENDING_SUBTASKS`); no open blockers; non-blank `delivery_summary` (`EMPTY_DELIVERY_SUMMARY`).

- [ ] **Step 1: Write the failing tests.** One per row above, plus: `test_review_gate_rejects_a_task_with_zero_criteria` (Review Focus 4), `test_whitespace_delivery_summary_fails` (Review Focus 3), `test_all_failures_are_reported_together`, `test_owner_is_not_subject_to_the_assignee_and_busy_gates` (an `OWNER` actor starting an unassigned task gets no `NOT_ASSIGNED_TO_ACTOR`), `test_ungated_targets_return_nothing` (`BACKLOG`, `DONE`, `CANCELLED`).
- [ ] **Step 2: Run to verify they fail.** `uv run pytest tests/domain/test_gates.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `GateContext` and `check_gates`.
- [ ] **Step 4: Run to verify.** `uv run pytest tests/domain -q`. Expected: pass.
- [ ] **Step 5: Commit.** `feat(domain): add the transition gates (BOOT-011)`.

### Task 4: PR A close-out (BOOT-011)

**Files:** Modify `docs/GLOSSARY.md`, `docs/bootstrap-tasks.md`, `docs/STATUS.md`.

- [ ] **Step 1: Document.** GLOSSARY: add `Decision` (`Allowed`/`Rejected`), `Rejection code`, `Gate failure`, `Approval request kinds` (delivery, cancellation), `Event type` with the English term and a Spanish mapping. Mark BOOT-011 `in_review`; rewrite STATUS (the `update-status` skill).
- [ ] **Step 2: Verify.** `python tools/check.py` from the repo root. Expected: 10 steps `PASS`.
- [ ] **Step 3: Commit, push, open the PR** (`feat: add the domain model, dependency graph and gates (BOOT-011)`), with the real `check` output in "How it was tested". Then `gh pr checks --watch`: `check` and `docker` green.

---

## PR B (branch `feat/BOOT-012-domain-policy`, from PR A's branch): Tasks 5 and 6

### Task 5: Transition policy (BOOT-012)

**Files:** Create `domain/policy.py`; test `tests/domain/test_policy.py`.

**Interfaces:**
- Consumes: Task 1 and 3 types, `check_gates`, `GateContext`.
- Produces: `Rule(source: Status, target: Status, actors: frozenset[ActorKind], agent_must_be_assignee: bool = False, gated: bool = False, requires_reason: bool = False, clears_assignment: bool = False)` frozen; `TRANSITION_RULES: tuple[Rule, ...]`; `decide_transition(task: Task, actor: Actor, target: Status, ctx: GateContext, *, reason: str | None = None, override_reason: str | None = None) -> Decision`.
- The rules mirror design §6.3. Owner means `{OWNER}`; "triage" means `{OWNER, ORCHESTRATOR}`:
  - `PROPOSED→BACKLOG`, `BACKLOG→READY` (gated): triage.
  - `READY→IN_PROGRESS` (gated), `IN_PROGRESS→IN_REVIEW` (gated): `{OWNER, AGENT}`, agent must be the assignee. `IN_PROGRESS→IN_REVIEW` also returns `Allowed.request = ApprovalRequest(task.id, DELIVERY, actor.id, task.delivery_summary)` and an `APPROVAL_REQUESTED` event.
  - `IN_REVIEW→DONE`: owner. `IN_REVIEW→READY` (return a delivery, reason required, keeps the assignment): owner.
  - `IN_PROGRESS→READY` (release, reason required, clears the assignment): `{OWNER, ORCHESTRATOR, AGENT}`, agent must be the assignee.
  - Backward moves, owner only: every pair where `ORDER.index(target) < ORDER.index(source)` not listed above, source in `PROPOSED..IN_REVIEW`; clears the assignment when the target is `PROPOSED` or `BACKLOG`.
  - `PROPOSED→CANCELLED` and cancelling any other open status: owner, clears the assignment.
  - Reopen `DONE`/`CANCELLED → BACKLOG` or `READY` (gated for `READY`): owner, reason required, clears the assignment.
- Behaviour: a `SYSTEM` actor, a missing rule, or an actor kind outside `actors` is `Rejected` (`NOT_PERMITTED` or `INVALID_TRANSITION`; same status is `INVALID_TRANSITION`). A missing or blank `reason` where required is `REASON_REQUIRED`. If gates fail: for an `OWNER` with a non-blank `override_reason` the decision is `Allowed` with a `GATE_OVERRIDDEN` event listing the failed gate codes and the reason; otherwise `Rejected(GATE_FAILED, gates=…)`. Agents and the orchestrator can never override. Every `Allowed` carries a `STATUS_CHANGED` event (payload `from`, `to`), plus `UNASSIGNED` when the assignment is cleared, and a warning for every `CANCELLED` blocker of the task (`ctx` does not carry them: add `cancelled_blockers: frozenset[str] = frozenset()` to `GateContext` here, a backward-compatible default).

- [ ] **Step 1: Write the failing tests.** `test_policy_matrix_matches_the_spec`: the test holds its own literal copy of the §6.3 table (rows: action, who may) and, for every `(source, target, ActorKind)` triple with an always-satisfied `GateContext` and a fully valid task, asserts `Allowed` exactly for the triples the table allows (Review Focus 1 and `SYSTEM` rejected). Then: `test_agent_cannot_start_a_task_assigned_to_someone_else`; `test_submit_creates_a_delivery_request`; `test_release_requires_a_reason_and_clears_the_assignment`; `test_return_keeps_the_assignment`; `test_gate_failure_rejects_an_agent_with_all_codes`; `test_owner_override_records_gate_overridden`; `test_owner_override_with_blank_reason_is_rejected`; `test_agent_override_reason_is_ignored`; `test_cancelled_blocker_adds_a_warning`.
- [ ] **Step 2: Run to verify they fail.** `uv run pytest tests/domain/test_policy.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `Rule`, `TRANSITION_RULES` (data, not branching code) and `decide_transition`.
- [ ] **Step 4: Run to verify.** `uv run pytest tests/domain -q`, `uv run pyright`. Expected: pass.
- [ ] **Step 5: Commit.** `feat(domain): add the transition policy table and decisions (BOOT-012)`.

### Task 6: Assignment and queue (BOOT-012)

**Files:** Create `domain/assignment.py`; test `tests/domain/test_assignment.py`.

**Interfaces:**
- Consumes: `Task`, `Actor`, `AgentProfile`, `Decision`.
- Produces: `decide_assign(task: Task, actor: Actor, agent: AgentProfile, load: int) -> Decision` (`load` = the agent's current `READY` plus `IN_PROGRESS` tasks) and `decide_unassign(task: Task, actor: Actor, reason: str | None) -> Decision`.
- `decide_assign`: actor `OWNER` or `ORCHESTRATOR` (else `NOT_PERMITTED`); task `READY` (else `WRONG_STATUS`); no current assignee (`ALREADY_ASSIGNED`); `task.type` in `agent.allowed_task_types` and `task.project_id` in `agent.allowed_project_ids` (`OUT_OF_SCOPE`); `load < agent.queue_limit` (`QUEUE_FULL`). On success the task gets the assignee and an `ASSIGNED` event. `decide_unassign`: same actors, task `READY` and assigned (`NOT_ASSIGNED`), non-blank reason (`REASON_REQUIRED`), `UNASSIGNED` event.

- [ ] **Step 1: Write the failing tests.** One per rejection code; `test_orchestrator_obeys_the_same_invariants` (scope and queue apply to it); `test_agent_cannot_assign_itself`; `test_full_queue_of_in_review_tasks_does_not_block` (the use case passes `load=0` for such an agent; the test documents that `load` counts only `READY` and `IN_PROGRESS`, Review Focus 5) and `test_load_at_the_limit_is_rejected`; `test_limit_is_per_agent` (`queue_limit=1`).
- [ ] **Step 2: Run to verify they fail.** `uv run pytest tests/domain/test_assignment.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** both functions.
- [ ] **Step 4: Run to verify.** `uv run pytest tests/domain -q`, `python tools/check.py`. Expected: pass, 10 steps `PASS`.
- [ ] **Step 5: Commit, push, open the PR** (`feat: add the transition policy and assignment (BOOT-012)`), base `feat/BOOT-011-domain-model` until PR A is merged. Mark BOOT-012 `in_review`.

---

## PR C (branch `feat/BOOT-013-domain-changes`, from PR B's branch): Tasks 7 to 9

### Task 7: Creating and changing tasks (BOOT-013)

**Files:** Create `domain/changes.py`; test `tests/domain/test_changes.py`.

**Interfaces:**
- Consumes: Task 1 types, `would_create_cycle`.
- Produces: `EDITABLE_FIELDS: frozenset[str]` (`title, description, type, priority, labels, parent_id, start_date, due_date, recurrence, criteria, subtasks, delivery_summary, working_notes`); `ASSIGNEE_FIELDS = frozenset({"delivery_summary", "working_notes"})`.
  - `decide_create(actor: Actor, profile: AgentProfile | None, draft: Task) -> Decision`: owner → status `BACKLOG`; agent or orchestrator → status `PROPOSED`, `OUT_OF_SCOPE` if `draft.type` or `draft.project_id` is outside `profile`, `NOT_PERMITTED` if `profile` is `None`; `SYSTEM` rejected. `created_by` is set to `actor.id`; an agent may draft criteria. Event `ITEM_CREATED`.
  - `decide_update_fields(task: Task, actor: Actor, changes: Mapping[str, object]) -> Decision`: keys outside `EDITABLE_FIELDS` are `FIELD_NOT_ALLOWED` (`status`, `assignee`, `blocked_by`, `id` have their own decisions). Owner: any editable field. Orchestrator: any editable field on a non-closed task. Agent: any editable field only while the task is `PROPOSED` and `created_by == actor.id`; otherwise only `ASSIGNEE_FIELDS`, and only when it is the assignee and the status is `IN_PROGRESS` (so after triage it cannot edit criteria, title, type, priority, dates, parent). Event `FIELDS_UPDATED` with the changed names.
  - `decide_attach_evidence(task: Task, actor: Actor, criterion_id: str, evidence: Evidence) -> Decision`: owner any time; the assignee agent only while `IN_PROGRESS`; blank content is `EMPTY_TEXT`; unknown criterion `UNKNOWN_CRITERION`; event `EVIDENCE_ATTACHED`.
  - `decide_comment(task: Task, actor: Actor, text: str) -> Decision`: owner and orchestrator always, the assignee agent on its own task; blank is `EMPTY_TEXT`; task unchanged, event `COMMENT_ADDED`.
  - `decide_add_dependency(task: Task, actor: Actor, blocker_id: str, blocked_by: Mapping[str, frozenset[str]]) -> Decision` and `decide_remove_dependency(task: Task, actor: Actor, blocker_id: str) -> Decision`: owner and orchestrator only; `DEPENDENCY_CYCLE` via `would_create_cycle`; `UNKNOWN_DEPENDENCY` when `blocker_id` is not a key of `blocked_by`; events `DEPENDENCY_ADDED` / `DEPENDENCY_REMOVED`.

- [ ] **Step 1: Write the failing tests.** Create: `test_owner_creates_in_backlog`, `test_agent_creates_a_proposal_inside_its_scope`, `test_agent_outside_scope_is_rejected`, `test_agent_can_draft_criteria_in_a_proposal`. Update: `test_agent_cannot_edit_criteria_after_triage`, `test_agent_can_edit_its_summary_while_in_progress`, `test_agent_cannot_change_title_type_priority_dates_parent_dependencies` (parametrized), `test_agent_cannot_edit_another_agents_task`, `test_protected_fields_are_rejected`. Evidence: `test_assignee_attaches_evidence_while_in_progress`, `test_blank_evidence_is_rejected`, `test_unknown_criterion`, `test_agent_cannot_attach_evidence_in_review`. Comment: `test_blank_comment_is_rejected`. Dependencies: `test_self_dependency_is_rejected`, `test_cycle_is_rejected`, `test_unknown_blocker_is_rejected`, `test_agent_cannot_change_dependencies`.
- [ ] **Step 2: Run to verify they fail.** `uv run pytest tests/domain/test_changes.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** the six functions.
- [ ] **Step 4: Run to verify.** `uv run pytest tests/domain -q`. Expected: pass.
- [ ] **Step 5: Commit.** `feat(domain): add task creation, field, evidence, comment and dependency decisions (BOOT-013)`.

### Task 8: Approval requests and visibility (BOOT-013)

**Files:** Create `domain/approval.py`, `domain/visibility.py`; tests `tests/domain/test_approval.py`, `test_visibility.py`.

**Interfaces:**
- Consumes: `decide_transition`, `GateContext`, `ApprovalRequest`.
- Produces: `decide_request_cancellation(task: Task, actor: Actor, reason: str | None, pending_exists: bool) -> Decision` (the assignee agent only, task not closed, non-blank reason `REASON_REQUIRED`, `DUPLICATE_REQUEST` if one is pending; `Allowed.request` is a pending `CANCELLATION` request, event `APPROVAL_REQUESTED`; the task is unchanged). `decide_resolve_request(task: Task, request: ApprovalRequest, actor: Actor, approve: bool, note: str | None, ctx: GateContext) -> Decision` (owner only; `REQUEST_NOT_PENDING`; approving a `DELIVERY` moves the task to `DONE`, rejecting it returns it to `READY` keeping the assignment and requires a non-blank note; approving a `CANCELLATION` moves it to `CANCELLED`, rejecting leaves it as is; both reuse `decide_transition` so the history events match; `Allowed.request` is the resolved request; event `APPROVAL_RESOLVED`). `can_view_task(actor: Actor, task: Task) -> bool` (owner and orchestrator see all; an agent sees tasks it is assigned or created; `SYSTEM` none).

- [ ] **Step 1: Write the failing tests.** `test_only_the_assignee_requests_cancellation`, `test_cancellation_needs_a_reason`, `test_duplicate_pending_request_is_rejected`, `test_agent_and_orchestrator_cannot_resolve` (Review Focus 1), `test_approving_a_delivery_marks_done`, `test_rejecting_a_delivery_needs_a_note_and_returns_to_ready`, `test_approving_a_cancellation_cancels`, `test_rejecting_a_cancellation_changes_nothing`, `test_resolving_twice_is_rejected`, `test_visibility_matrix`.
- [ ] **Step 2: Run to verify they fail.** `uv run pytest tests/domain/test_approval.py tests/domain/test_visibility.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** the three functions.
- [ ] **Step 4: Run to verify.** `uv run pytest tests/domain -q`. Expected: pass.
- [ ] **Step 5: Commit.** `feat(domain): add approval requests and visibility (BOOT-013)`.

### Task 9: Property-based invariants and close-out (BOOT-013)

**Files:** Create `tests/domain/test_domain_properties.py`; modify `CLAUDE.md` (code status: domain tests), `docs/bootstrap-tasks.md`, `docs/STATUS.md`, `docs/ROADMAP.md`.

- [ ] **Step 1: Write the failing tests** with Hypothesis (`@given` and one `RuleBasedStateMachine` named `KairosWorld`). The machine holds a small world (one owner, two agents with scopes and `queue_limit=2`, one orchestrator, up to six tasks) and rules that call the real decision functions with random actors, targets and fields, applying only `Allowed` results (keeping `load`, `other_in_progress`, `open_blockers` consistent with the world, as a use case would). Invariants checked after every step:
  1. no agent has more than one `IN_PROGRESS` task; no task has more than one assignee;
  2. each agent's `READY` plus `IN_PROGRESS` count never exceeds its `queue_limit`;
  3. `blocked_by` is acyclic;
  4. a task reaches `DONE`, `CANCELLED` or is reopened only through an action whose actor was `OWNER` (the world logs the actor of every status change);
  5. every task that reached `IN_REVIEW` by an agent had all criteria with evidence at that moment (unless the log shows a `GATE_OVERRIDDEN` by the owner);
  6. an agent never holds a task outside its allowed types and projects.
  Plus properties: `test_non_owner_never_closes_or_deletes` (random `(source, target, actor kind, reason, override_reason)` never gives `Allowed` for `DONE`, `CANCELLED` or a backward move unless `OWNER`) and `test_every_decision_is_allowed_or_rejected` (no exceptions for arbitrary inputs).
- [ ] **Step 2: Run to verify** the tests exercise real behaviour: temporarily break one rule (for example allow `AGENT` on `IN_REVIEW→DONE` in `TRANSITION_RULES`) and run `uv run pytest tests/domain/test_domain_properties.py -q`. Expected: FAIL with a shrunk counterexample; revert the change.
- [ ] **Step 3: Fix** anything the properties expose in the domain (each real finding gets its own test first), then restore green.
- [ ] **Step 4: Document.** `CLAUDE.md` "Code status": the domain exists (`backend/src/kairos/domain/`), its tests run in `uv run pytest -q`. Mark BOOT-011 to BOOT-013 `done` or `in_review`, tick slice 1 in `docs/ROADMAP.md`, rewrite `docs/STATUS.md`.
- [ ] **Step 5: Verify.** `python tools/check.py`: 10 steps `PASS`.
- [ ] **Step 6: Commit, push, open the PR** (`feat: add approval requests, task changes and domain properties (BOOT-013)`); then one independent whole-branch review of the three PRs together before the owner merges the last one.
