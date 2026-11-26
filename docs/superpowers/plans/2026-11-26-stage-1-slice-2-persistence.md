# Stage 1, Slice 2: Persistence and History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist what the domain decides: SQLite schema and migrations, repositories, use cases that apply every `decide_*` function in one transaction, and the hash-chained, append-only `events` log with a `verify` command.

**Architecture:** The domain stays pure and untouched by storage. `adapters/db/` owns the engine, schema and migrations (SQLAlchemy 2 Core, synchronous, no ORM: the domain dataclasses are the model). `features/history/` owns hashing, appending and verifying events. `features/tasks/` and `features/registry/` hold the repositories and the use cases (`TaskService`, `RegistryService`): each loads state, builds the `GateContext`, calls a `decide_*` function and, if `Allowed`, writes the new state, the request and the events in one `BEGIN IMMEDIATE` transaction; if `Rejected`, nothing is written.

**Tech Stack:** Python 3.13, SQLAlchemy 2 (Core), Alembic, SQLite (WAL), pytest, Hypothesis, Ruff, pyright strict. All commands from `backend/` with `uv`.

**Spec:** [`../specs/2026-11-26-kairos-design.md`](../specs/2026-11-26-kairos-design.md) (§6.8, §6.10, §7, §14) and [`../specs/2026-11-26-stage-1-decomposition-design.md`](../specs/2026-11-26-stage-1-decomposition-design.md) (slice 2). ADR-0002, ADR-0003, ADR-0006. Vocabulary: `docs/GLOSSARY.md`.

## Global Constraints

- `domain/` keeps importing only the standard library and itself (the purity test stays green). SQLAlchemy and Alembic are imported only under `adapters/db/` and `features/*/repository.py`, `unit_of_work.py`.
- Every state change and its events are written **in the same transaction** (ADR-0006). Writes use `BEGIN IMMEDIATE`; the database runs in WAL mode with `foreign_keys=ON` (ADR-0002).
- `events` is append-only: no code path issues `UPDATE` or `DELETE` on it, and database triggers reject both (golden rule 3).
- Clock and ids are injected (`Clock = Callable[[], datetime]` returning UTC-aware values, `NewId = Callable[[], str]`); no use case calls `datetime.now()` or `uuid` directly, so tests are deterministic.
- Python 3.13; pyright **strict** and Ruff clean on `src` and `tests`. English everywhere. Names follow `docs/GLOSSARY.md`.
- TDD, red then green. `python tools/check.py` green before each PR. Git: three branches from `origin/main`, **not stacked** (the owner merges each before the next starts; stacked squash merges lost PRs B and C of slice 1); one worktree `../Kairos-wt/BOOT-015`, reused; Conventional Commits; `git add <file>` by name; never `--no-verify`; the owner squash-merges.
- Out of scope: HTTP, tokens, sessions, login, the UI, SSE, backups, project lifecycle changes, human-readable task numbers, container progress queries.

## My calls (the design leaves them to the builder; record any change in the ledger)

- **SQLAlchemy Core, no ORM** (the owner left the choice to me): the domain objects are frozen dataclasses, and an ORM would need a second, mutable model. Rows map to the frozen domain dataclasses by hand in the repositories; a round-trip property test guards the mapping.
- **One `items` table** (design §6.1 recommendation) for projects, epics, tasks and subtasks, with `kind` and `parent_id`. Task-only columns are nullable and a `CHECK` ties them to `kind`. Criteria, evidence, dependencies, comments and approval requests have their own tables. Evidence and dependency rows are replaced wholesale on save (at most ~200 tasks).
- **Subtasks get identity and a kanban status** (decided with the owner; design §6.1 and §17.1 amended in PR A): `Subtask(id, title, status)` with `SubtaskStatus` = `TODO`, `IN_PROGRESS`, `IN_REVIEW` (pending approval), `DONE`, `CANCELLED`. Owner, orchestrator and the agent carrying the task (while it is `IN_PROGRESS`; a subagent is the same agent, recorded as `via`) move a subtask freely among `TODO`, `IN_PROGRESS` and `IN_REVIEW`. Only the owner moves it to `DONE` or `CANCELLED` or reopens it to `TODO` (with a reason): golden rule 2. The review gate rejects a task with a subtask in `TODO` or `IN_PROGRESS`; a subtask `IN_REVIEW` does not block, and approving the delivery moves those subtasks to `DONE` with their own events. Owner and orchestrator add subtasks (as `TODO`); an agent only inside its own proposal. `subtasks` stops being an editable field. More statuses later are a migration plus one rule row.
- **Projects, epics and agent profiles** are created by the owner only, through domain decisions in a new `domain/registry.py`, so no rule lives in a use case. Epic status is not stored. Agent tokens arrive in slice 4 (`agents` holds the profile only).
- **Task types** are rows seeded by the baseline migration: `bug` (requires `description`), `feature` (`description`, `priority`), `chore` (none), `research` (`description`), `personal` (none). The design fixes the idea, not the values.
- **The event hash** is `sha256(prev_hash + canonical_json(record))` in hex, where the record is `{seq, id, at, actor_kind, actor_id, via, entity_id, type, payload, reason}` and canonical JSON means `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`. The first event has `prev_hash` of 64 zeros. A trigger also rejects an insert whose `prev_hash` is not the last stored hash.
- **Rejections are not logged** (the log records changes, not attempts). A task the actor may not see answers `NOT_FOUND`, the same as a missing one.
- **Migrations run at startup** (`create_app` lifespan) against `<data_dir>/kairos.db`. Tests build databases from a migrated template file copied per test.

## Review Focus

1. A rejected decision leaves no trace: no changed row and no event, for every use case, and for the full sequence "reject after a successful read". Task 7.
2. If appending events fails after the task row was written, the task row is rolled back too (atomicity), and a second connection never sees a half-written change. Task 7.
3. Tampering is detected: editing a payload, deleting a middle event, swapping two events and truncating a prefix each make `verify` fail with the first broken `seq`; an empty log verifies. Task 5.
4. An agent or the orchestrator cannot approve, cancel or delete through any `TaskService` method (subtasks included: no `DONE` or `CANCELLED` for them), whatever the arguments, and the database holds no row they changed. Task 9.
5. The database refuses what the domain already refuses: two `IN_PROGRESS` tasks for one agent, two pending requests for one task, an unknown status, a task without a project, an `UPDATE` or `DELETE` on `events`. Task 3.

## File structure

```
backend/src/kairos/domain/         model.py gates.py changes.py decision.py events.py edited; registry.py new
backend/src/kairos/adapters/       runtime.py (Clock, NewId, defaults)
backend/src/kairos/adapters/db/    engine.py schema.py migrate.py migrations/ (env.py, versions/0001_baseline.py)
backend/src/kairos/features/history/   hashing.py log.py verify.py __main__.py
backend/src/kairos/features/tasks/     repository.py unit_of_work.py service.py queries.py
backend/src/kairos/features/registry/  repository.py service.py
backend/tests/db/ tests/history/ tests/tasks/ tests/registry/   (test basenames unique across tests/)
```

---

## PR A (branch `feat/BOOT-015-domain-registry`): Tasks 1 and 2

### Task 1: Subtasks with identity and a kanban status (BOOT-015)

**Files:** Create `domain/subtasks.py`, `tests/domain/test_subtasks.py`. Modify `domain/status.py` (`SubtaskStatus`), `domain/model.py`, `domain/gates.py`, `domain/changes.py` (`subtasks` leaves `EDITABLE_FIELDS`; `decide_create` validates drafted subtasks), `domain/approval.py` (the cascade), `domain/events.py`, `domain/decision.py`; the existing tests that use `SubtaskStatus.PENDING` (`test_gates.py`, `test_domain_properties.py`) and the design doc Â§6.1, Â§17.1.

**Interfaces (produces):**
- `SubtaskStatus`: `TODO`, `IN_PROGRESS`, `IN_REVIEW`, `DONE`, `CANCELLED` (`PENDING` is replaced by `TODO`, value `"todo"`). `SUBTASK_OPEN = frozenset({TODO, IN_PROGRESS})` blocks the review gate.
- `Subtask(id: str, title: str, status: SubtaskStatus = SubtaskStatus.TODO)` frozen dataclass in `model.py`; `Task.subtasks: tuple[Subtask, ...]`.
- `SUBTASK_RULES: tuple[SubtaskRule, ...]` in `subtasks.py`, one data table like `TRANSITION_RULES` (`source`, `target`, `actors`, `requires_reason`): workers `{owner, orchestrator, agent}` for every ordered pair among `TODO`, `IN_PROGRESS`, `IN_REVIEW`; owner only for `* â†’ DONE` and `* â†’ CANCELLED` from any open status; owner only, with a reason, for `DONE|CANCELLED â†’ TODO`.
- `decide_add_subtask(task: Task, actor: Actor, subtask: Subtask) -> Decision`: owner or orchestrator, or the agent that created the task while it is `PROPOSED`; rejects a blank title (`EMPTY_TEXT`), a status other than `TODO` (`FIELD_NOT_ALLOWED`), a duplicate id (`DUPLICATE_SUBTASK`), a closed task (`WRONG_STATUS`); event `SUBTASK_ADDED`.
- `decide_move_subtask(task: Task, actor: Actor, subtask_id: str, target: SubtaskStatus, *, reason: str | None = None) -> Decision`: interprets the table; an agent must be `task.assignee` and the task `IN_PROGRESS` (otherwise `NOT_ASSIGNED` or `WRONG_STATUS`); owner and orchestrator need a non-closed task; unknown id `UNKNOWN_SUBTASK`; a pair no actor may perform `INVALID_TRANSITION`, a pair another actor kind may perform `NOT_PERMITTED`; missing reason `REASON_REQUIRED`; event `SUBTASK_STATUS_CHANGED` with `{subtask, from, to}`.
- `approve_pending_subtasks(task: Task, actor: Actor) -> tuple[Task, tuple[Event, ...]]`: every `IN_REVIEW` subtask becomes `DONE`, one event each; `decide_resolve_request` calls it when the owner approves a delivery. Rejecting a delivery leaves subtasks as they are.
- New codes: `RejectionCode.UNKNOWN_SUBTASK`, `DUPLICATE_SUBTASK`; new `EventType.SUBTASK_ADDED`, `SUBTASK_STATUS_CHANGED`. The `PENDING_SUBTASKS` gate fires when any subtask is in `SUBTASK_OPEN`.

- [ ] **Step 1: Write the failing tests** in `tests/domain/test_subtasks.py`: a table-driven test over (actor kind Ã— source Ã— target) against a hand-written copy of the rules above (the agent column assumes it carries the task in `IN_PROGRESS`); the owner adds a subtask and gets `SUBTASK_ADDED`; the orchestrator adds one; an agent adding one to an assigned task is `NOT_PERMITTED`, but may inside its own `PROPOSED` task; a duplicate id and a non-`TODO` status are rejected; the assigned agent moves `TODO â†’ IN_PROGRESS â†’ IN_REVIEW`, a subagent actor (`via` set) too, and the event carries `via`; the same agent moving to `DONE` or `CANCELLED` is rejected, as is the orchestrator; another agent, or the carrying agent on a `READY` task, is rejected; reopening needs a reason; `decide_update_fields` rejects `{"subtasks": ...}` for every actor kind with `FIELD_NOT_ALLOWED`; the review gate fails with a `TODO` or `IN_PROGRESS` subtask and passes with `IN_REVIEW`, `DONE` and `CANCELLED` ones; approving a delivery turns `IN_REVIEW` subtasks into `DONE` (with events) and leaves the others, and rejecting it changes none; `decide_create` rejects a drafted subtask that is not `TODO` or has a duplicate id.
- [ ] **Step 2: Run** `uv run pytest tests/domain -q`. Expected: the new tests fail, and existing ones that use `SubtaskStatus.PENDING` or a tuple of statuses fail to import or type-check.
- [ ] **Step 3: Implement** the model change, `subtasks.py`, the gate, the cascade, the codes and event types; migrate the existing tests and the Hypothesis strategies to `Subtask`, and extend the "agents never reach `DONE` or `CANCELLED`" property to subtasks.
- [ ] **Step 4: Run** `uv run pytest -q`, `uv run pyright` and `uv run ruff check --config pyproject.toml . ../tools`. Expected: all pass, 0 errors.
- [ ] **Step 5: Commit** `feat(domain): give subtasks an identity and a kanban status (BOOT-015)`.

### Task 2: Registry decisions and `NOT_FOUND`

**Files:** Create `domain/registry.py`, `tests/domain/test_registry.py`; modify `domain/decision.py` (`RejectionCode.NOT_FOUND`), `domain/events.py` (`AGENT_REGISTERED`).

**Interfaces (produces):**
- `Project(id: str, title: str, area: str, status: ProjectStatus = ProjectStatus.ACTIVE)`, `Epic(id: str, project_id: str, title: str)` frozen dataclasses (`ProjectStatus` already exists in `status.py`).
- `Created[T](item: T, events: tuple[Event, ...])` and `type RegistryDecision[T] = Created[T] | Rejected`.
- `decide_create_project(actor: Actor, project: Project) -> RegistryDecision[Project]`, `decide_create_epic(actor: Actor, epic: Epic, project_exists: bool) -> RegistryDecision[Epic]`, `decide_register_agent(actor: Actor, profile: AgentProfile) -> RegistryDecision[AgentProfile]`. Owner only (`NOT_PERMITTED` otherwise, including the orchestrator); blank titles or ids `EMPTY_TEXT`; unknown project `NOT_FOUND`; a profile whose kind is not `AGENT` or `ORCHESTRATOR`, or with `queue_limit < 1`, `FIELD_NOT_ALLOWED`. Events: `ITEM_CREATED` for projects and epics, `AGENT_REGISTERED` for profiles.

- [ ] **Step 1: Write the failing tests** (table-driven over actor kind × decision: only the owner gets `Created`; the rest `NOT_PERMITTED`; blank title, missing project and bad profile cases).
- [ ] **Step 2: Run** `uv run pytest tests/domain/test_registry.py -q`. Expected: FAIL, module missing.
- [ ] **Step 3: Implement** `registry.py` and the two enum members.
- [ ] **Step 4: Run** `uv run pytest -q`, `uv run pyright`, `uv run ruff check --config pyproject.toml . ../tools`. Expected: clean.
- [ ] **Step 5: Commit** `feat(domain): add owner-only registry decisions (BOOT-015)`; run `python tools/check.py`, open PR A.

---

## PR B (branch `feat/BOOT-016-db-and-history`): Tasks 3 to 5

### Task 3: Engine, schema and migrations (BOOT-016)

**Files:** Create `adapters/db/engine.py`, `schema.py`, `migrate.py`, `migrations/env.py`, `migrations/script.py.mako`, `migrations/versions/0001_baseline.py`; `tests/db/test_engine.py`, `test_schema.py`, `test_migrations.py`; modify `tests/conftest.py` (fixtures), `config.py` (`database_path` property: `data_dir / "kairos.db"`). Add dependencies with `uv add --project backend sqlalchemy alembic` (commit `uv.lock`).

**Interfaces (produces):**
- `make_engine(path: Path | None) -> Engine`: `None` gives an in-memory engine with `StaticPool`; a path gives a file engine. On connect: `PRAGMA journal_mode=WAL` (file only), `foreign_keys=ON`, `busy_timeout=5000`; transactions start with `BEGIN IMMEDIATE` (the pysqlite `isolation_level=None` listener recipe).
- `schema.metadata: MetaData` with tables `items`, `criteria`, `evidence`, `dependencies`, `comments`, `approval_requests`, `agents`, `task_types`, `events`.
- `upgrade(engine: Engine) -> None` and `downgrade(engine: Engine, revision: str) -> None` in `migrate.py` (programmatic Alembic `Config`, `script_location` is the package folder, so no `alembic.ini`).
- Fixtures: `migrated_engine` (a template database migrated once per session, copied per test) and `conn` (a transaction-scoped connection).

Schema rules the migration must enforce (each has a test in Step 1):
- `items(kind, status)` `CHECK`s on the allowed values; task-only columns (`type`, `priority`, `assignee_id`, `delivery_summary`, ...) are `NULL` unless `kind='task'`; a task has a non-null `project_id`; `assignee_id` references `agents(id)`.
- **Partial unique index** `one_in_progress_per_agent` on `items(assignee_id) WHERE kind='task' AND status='in_progress'`.
- **Partial unique index** `one_pending_request_per_task` on `approval_requests(task_id) WHERE state='pending'`.
- `events(seq INTEGER PRIMARY KEY AUTOINCREMENT, id, at, actor_kind, actor_id, via, entity_id, type, payload, reason, prev_hash, hash)`; triggers `events_no_update` and `events_no_delete` (`RAISE(ABORT, 'events is append-only')`) and `events_chain_check` (`BEFORE INSERT`, aborts when `NEW.prev_hash` differs from the last `hash`, or from 64 zeros on an empty table).
- The five task types are inserted by the migration.

- [ ] **Step 1: Write the failing tests:** WAL on a file engine and foreign keys on both; two raw inserts of `IN_PROGRESS` tasks for one agent raise `IntegrityError`; two pending requests for one task raise; an unknown status raises; `UPDATE events` and `DELETE FROM events` raise `'events is append-only'`; an event insert with a wrong `prev_hash` raises; `upgrade` then `downgrade("base")` then `upgrade` works; `alembic.autogenerate.compare_metadata` between the migrated database and `schema.metadata` returns `[]`; the five task types exist.
- [ ] **Step 2: Run** `uv run pytest tests/db -q`. Expected: FAIL, modules missing.
- [ ] **Step 3: Implement** the three modules, the migration and the fixtures. `schema.py` is the single description of the tables; the migration is written out by hand (not imported from `schema.py`) so a later schema change cannot rewrite history, and the drift test keeps both honest.
- [ ] **Step 4: Run** `uv run pytest -q`, `uv run pyright`. Expected: pass, 0 errors.
- [ ] **Step 5: Commit** `feat(db): add the SQLite engine, schema and baseline migration (BOOT-016)`.

### Task 4: Event hashing and append

**Files:** Create `features/history/hashing.py`, `features/history/log.py`; tests `tests/history/test_hashing.py`, `tests/history/test_log.py`.

**Interfaces (produces):**
- `GENESIS_HASH: str` (64 zeros); `canonical_json(value: Mapping[str, object]) -> str`; `event_hash(prev_hash: str, record: Mapping[str, object]) -> str`.
- `EventRecord` frozen dataclass: `seq: int, id: str, at: datetime, actor_kind: ActorKind, actor_id: str, via: str | None, entity_id: str, type: EventType, payload: Mapping[str, object], reason: str | None, prev_hash: str, hash: str`.
- `append_events(conn: Connection, events: Sequence[Event], at: datetime, new_id: NewId) -> list[EventRecord]`: reads the last hash inside the caller's transaction, inserts in order, chains each hash on the previous one. It never commits.
- `list_events(conn: Connection, *, entity_id: str | None = None, after_seq: int = 0, limit: int = 100) -> list[EventRecord]`, ordered by `seq`.

- [ ] **Step 1: Write the failing tests:** `canonical_json` ignores key order and is stable for unicode; two `event_hash` calls with different `prev_hash` differ; a fixed record has a pinned expected hex (a golden value written into the test, so the format cannot drift silently); appending three events chains `prev_hash` correctly and the first uses `GENESIS_HASH`; `via` and `reason` round-trip; `list_events` filters by entity and pages by `after_seq`; appending inside a rolled-back transaction leaves the log empty.
- [ ] **Step 2: Run** `uv run pytest tests/history -q`. Expected: FAIL, modules missing.
- [ ] **Step 3: Implement** `hashing.py` (pure, standard library) and `log.py`.
- [ ] **Step 4: Run** `uv run pytest -q`. Expected: pass.
- [ ] **Step 5: Commit** `feat(history): append hash-chained events in the caller's transaction (BOOT-016)`.

### Task 5: `verify` and its command

**Files:** Create `features/history/verify.py`, `features/history/__main__.py`; tests `tests/history/test_verify.py`, `tests/history/test_verify_command.py`.

**Interfaces (produces):**
- `VerifyResult(ok: bool, checked: int, broken_at: int | None, reason: str | None)` frozen dataclass.
- `verify_chain(conn: Connection) -> VerifyResult`: recomputes every hash from `seq` 1 and checks each `prev_hash`; the first mismatch gives `broken_at` and a `reason` (`"hash mismatch"`, `"broken link"` or `"first event does not start the chain"`).
- `main(argv: Sequence[str] | None = None) -> int`: `python -m kairos.features.history [--data-dir PATH]` opens `<data-dir>/kairos.db` read-only, prints `OK: <n> events verified` or `BROKEN at seq <n>: <reason>`, returns `0` or `1`; a missing database returns `2` with a message.

- [ ] **Step 1: Write the failing tests** (Review Focus 3): build a log of five events through `append_events`, then in separate tests drop the three triggers on the test database only, tamper (edit a payload, delete the third event, swap two rows' payloads, delete the first event) and assert `verify_chain` reports the expected `broken_at`; an untouched log and an empty log are `ok`; the command returns `0`, `1` and `2` on the three situations and prints the lines above.
- [ ] **Step 2: Run** `uv run pytest tests/history/test_verify.py tests/history/test_verify_command.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** both modules. Truncating the *tail* cannot be detected by a chain alone (ADR-0006 says the chain detects tampering, not everything): say so in the `verify_chain` docstring.
- [ ] **Step 4: Run** `uv run pytest -q`, `uv run pyright`. Expected: pass.
- [ ] **Step 5: Add** the `verify` row to the commands table of `CLAUDE.md` (only now that it exists and was run), commit `feat(history): verify the event chain and add the verify command (BOOT-016)`; run `python tools/check.py`, open PR B.

---

## PR C (branch `feat/BOOT-017-use-cases`): Tasks 6 to 9

### Task 6: Repositories (BOOT-017)

**Files:** Create `features/tasks/repository.py`, `features/registry/repository.py`; tests `tests/tasks/test_repository.py`.

**Interfaces (produces; both take a `Connection` and never commit):**
- `TaskRepository`: `get(task_id) -> Task | None`; `save(task: Task) -> None` (upsert the item, replace its criteria, evidence, dependencies and subtasks); `get_pending_request(task_id) -> ApprovalRequest | None`; `save_request(request: ApprovalRequest) -> None` (insert a new row, or update the pending one when `state` changed); `get_task_type(name) -> TaskType | None`; `blocked_by_map() -> dict[str, frozenset[str]]`; `statuses(ids: Iterable[str]) -> dict[str, Status]`; `other_in_progress(agent_id: str, excluding: str) -> frozenset[str]`; `load(agent_id: str) -> int` (assigned tasks in `READY` or `IN_PROGRESS`); `list(*, status: Status | None, assignee: str | None) -> list[Task]`; `add_comment(task_id, author, text, at)` and `comments(task_id)`.
- `RegistryRepository`: `save_project`, `save_epic`, `project_exists(id) -> bool`, `save_agent`, `get_agent(id) -> AgentProfile | None`, `list_agents()`.

- [ ] **Step 1: Write the failing tests:** a Hypothesis round trip (`save` then `get` equals the task) over tasks with criteria, evidence, subtasks, dependencies, dates and labels; `blocked_by_map`, `other_in_progress` (excludes the given task and other agents' tasks) and `load` (does not count `IN_REVIEW`) on a small fixture; saving the same task twice does not duplicate children; a foreign-key violation (task with an unknown project) raises.
- [ ] **Step 2: Run** `uv run pytest tests/tasks/test_repository.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** both repositories with SQLAlchemy Core and explicit row mapping.
- [ ] **Step 4: Run** `uv run pytest -q`, `uv run pyright`. Expected: pass.
- [ ] **Step 5: Commit** `feat(tasks): add the task and registry repositories (BOOT-017)`.

### Task 7: Unit of work and `TaskService`

**Files:** Create `features/tasks/unit_of_work.py`, `features/tasks/service.py`; tests `tests/tasks/test_service_commands.py`, `tests/tasks/test_service_atomicity.py`.

**Interfaces (produces):**
- `UnitOfWork` context manager over one engine connection with `BEGIN IMMEDIATE`: exposes `tasks`, `registry`, `conn`; commits on a clean exit, rolls back on an exception or when `rollback()` was called.
- `Clock`, `NewId` type aliases in `kairos/adapters/runtime.py`, plus `system_clock()` and `uuid_ids()` defaults.
- `TaskService(engine: Engine, clock: Clock, new_id: NewId)` with one method per use case, each returning `Decision` (`Allowed` carrying the persisted task, `Rejected` otherwise): `create_task(actor, draft)`, `move_task(actor, task_id, target, *, reason=None, override_reason=None)`, `assign_task(actor, task_id, agent_id)`, `unassign_task(actor, task_id, reason)`, `update_fields(actor, task_id, changes)`, `attach_evidence(actor, task_id, criterion_id, evidence)`, `comment(actor, task_id, text)`, `add_dependency(actor, task_id, blocker_id)`, `remove_dependency(actor, task_id, blocker_id)`, `add_subtask(actor, task_id, subtask)`, `move_subtask(actor, task_id, subtask_id, target, *, reason=None)`, `request_cancellation(actor, task_id, reason)`, `resolve_request(actor, task_id, approve, note)`. A missing task or agent returns `Rejected(NOT_FOUND)`; an agent profile is loaded for the actor when it is an agent or the orchestrator.
- One private `_apply(uow, decision)`: on `Allowed` it saves the task, saves the request when present, appends the events and returns the decision; on `Rejected` it calls `uow.rollback()`.

- [ ] **Step 1: Write the failing tests** (Review Focus 1 and 2): for each method a happy path (row changed, the expected events appear in `list_events`, `verify_chain` is `ok`) and a rejected path (the table contents and the event count are identical before and after); `GateContext` is built from the database: an open blocker rejects `IN_PROGRESS` with `OPEN_DEPENDENCIES`, a cancelled blocker passes with a warning; a task in `IN_PROGRESS` for the same agent rejects the second with `AGENT_BUSY`; `request_cancellation` then `resolve_request(approve=True)` cancels and clears the assignment; moving to `IN_REVIEW` creates the delivery request; a fault injected into `append_events` (monkeypatch to raise) leaves the task row unchanged; two services on two connections racing to start two tasks of the same agent: one wins, the other gets a `Rejected` or the database error is translated to `AGENT_BUSY`.
- [ ] **Step 2: Run** `uv run pytest tests/tasks -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `unit_of_work.py`, `runtime.py` and `service.py`. Translate an `IntegrityError` on `one_in_progress_per_agent` into `Rejected(AGENT_BUSY)`; any other `IntegrityError` propagates.
- [ ] **Step 4: Run** `uv run pytest -q`, `uv run pyright`. Expected: pass.
- [ ] **Step 5: Commit** `feat(tasks): apply every domain decision in one transaction (BOOT-017)`.

### Task 8: Registry service, queries and app wiring

**Files:** Create `features/registry/service.py`, `features/tasks/queries.py`; modify `main.py` (lifespan), `config.py` if needed; tests `tests/registry/test_registry_service.py`, `tests/tasks/test_queries.py`, `tests/test_app_database.py`.

**Interfaces (produces):**
- `RegistryService(engine, clock, new_id)`: `create_project(actor, project)`, `create_epic(actor, epic)`, `register_agent(actor, profile)`, each returning `RegistryDecision[...]`, writing events the same way as `TaskService`.
- `TaskQueries(engine)`: `get_task(actor, task_id) -> Task | Rejected` (uses `can_view_task`; invisible equals missing, `NOT_FOUND`), `list_tasks(actor, *, status=None, assignee=None) -> list[Task]` (filtered by `can_view_task`), `pending_requests(actor) -> list[ApprovalRequest]` (owner and orchestrator only; an agent gets an empty list), `task_history(actor, task_id) -> list[EventRecord] | Rejected`.
- `create_app` runs `upgrade(engine)` in its lifespan for `settings.database_path`, creates the engine once and keeps `TaskService`, `RegistryService` and `TaskQueries` in `app.state`. No route uses them yet.

- [ ] **Step 1: Write the failing tests:** only the owner creates projects, epics and agents (others rejected, no event); an agent sees only its assigned tasks and the unassigned ones it created, the orchestrator and the owner see all; `pending_requests` is empty for an agent; `task_history` of an invisible task is `NOT_FOUND`; starting the app with a temp `data_dir` creates `kairos.db` at schema head and `/api/health` still answers; starting it twice does not fail.
- [ ] **Step 2: Run** `uv run pytest tests/registry tests/tasks/test_queries.py tests/test_app_database.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** the three modules and the lifespan.
- [ ] **Step 4: Run** `uv run pytest -q`, `uv run pyright`. Expected: pass.
- [ ] **Step 5: Commit** `feat(registry): add the registry service, visibility-filtered queries and DB startup (BOOT-017)`.

### Task 9: Invariants through the database, docs and Docker check

**Files:** Create `tests/tasks/test_service_lifecycle.py`, `tests/tasks/test_service_boundaries.py`, `tests/tasks/test_service_properties.py`; modify `docs/STATUS.md`, `docs/ROADMAP.md`, `docs/GLOSSARY.md` (if a new term appeared), `docs/bootstrap-tasks.md`.

- [ ] **Step 1: Write the failing tests:** (a) the lifecycle: owner creates a project and a task, orchestrator triages and assigns, agent starts, moves a subtask to `IN_REVIEW`, attaches evidence, submits, owner approves (the subtask becomes `DONE`); the log has the expected event types in order and `verify_chain` is `ok`. (b) Review Focus 4: parametrized over every `TaskService` method and over the agent and orchestrator actors, with arguments aimed at approving, cancelling or reaching `DONE`/`CANCELLED`: each returns `Rejected` and leaves tables and the event count untouched. (c) A Hypothesis rule-based state machine over `TaskService` (owner, orchestrator and two agents; `max_examples=25`, `stateful_step_count=20`) asserting after every step: the chain verifies, no agent has two `IN_PROGRESS` tasks, no task has two pending requests, and every task row equals the state replayed from its `status_changed`, `assigned` and `unassigned` events.
- [ ] **Step 2: Run** `uv run pytest tests/tasks -q`. Expected: FAIL on the new files only if a gap exists; fix the gap test-first, never by loosening the assertion.
- [ ] **Step 3: Run the whole check** `python tools/check.py` from the repo root. Expected: `check: OK`.
- [ ] **Step 4: Verify in Docker:** `docker compose up -d --wait`; then `docker compose exec kairos python -m kairos.features.history`. Expected: `OK: 0 events verified`, and `/data/kairos.db` exists in the volume. Stop with `docker compose down` (never `-v`).
- [ ] **Step 5: Rewrite** `docs/STATUS.md` (use the `update-status` skill), update `ROADMAP.md` and `bootstrap-tasks.md`, record the independent review of the whole slice before PR C is merged; commit `docs: close slice 2 (BOOT-017)`; run `python tools/check.py`, open PR C.

## Self-review notes

- **Spec coverage:** §6.8 invariants (partial unique index, scope, queue via `load`) → Tasks 3, 6, 7; §6.10 and ADR-0006 (same transaction, triggers, `verify`) → Tasks 3 to 5, 7; §7 defense in depth → Task 3; §14 integration tests with in-memory SQLite and property tests → Tasks 6 and 9; the decomposition's "use cases that apply domain decisions" → Tasks 7 and 8.
- **Not covered here, on purpose:** REST, auth, MCP and UI (slices 3 to 6); project lifecycle changes and container progress queries (read models arrive with the board, stage 2); hashing of the *tail* (see Task 5).
