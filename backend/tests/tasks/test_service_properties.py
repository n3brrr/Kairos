"""A state machine plays the use cases at random; after every step the database must hold."""

import shutil
import tempfile
from collections import Counter
from pathlib import Path

from hypothesis import HealthCheck, settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine,
    initialize,
    invariant,
    rule,
    run_state_machine_as_test,
)

from kairos.adapters.db.engine import make_engine
from kairos.domain.actor import Actor, ActorKind
from kairos.domain.events import EventType
from kairos.domain.model import Criterion, Evidence, EvidenceKind, Subtask, Task
from kairos.domain.status import CLOSED, Status, SubtaskStatus

from .support import make_env

OWNER = Actor(ActorKind.OWNER, "owner")
ORCH = Actor(ActorKind.ORCHESTRATOR, "o1")
A1 = Actor(ActorKind.AGENT, "a1")
A2 = Actor(ActorKind.AGENT, "a2")
SUBAGENT = Actor(ActorKind.AGENT, "a1", via="helper")
ACTORS = [OWNER, ORCH, A1, A2, SUBAGENT]
TASK_IDS = ["t1", "t2", "t3"]
PROOF = Evidence(EvidenceKind.TEXT, "ok", "a1")
CHANGES: list[dict[str, object]] = [
    {"title": "Renamed"},
    {"criteria": (Criterion("c1", "It works"),)},
    {"delivery_summary": "Done"},
    {"working_notes": "notes"},
    {"status": Status.DONE},  # never an editable field
    {"assignee": "a1"},  # nor this one
]

# What the random walk reached, over every example: the walk must get past the first statuses.
COVERAGE: Counter[str] = Counter()


class Machine(RuleBasedStateMachine):
    template: Path

    def __init__(self) -> None:
        super().__init__()
        self.dir = Path(tempfile.mkdtemp(prefix="kairos-machine-"))
        shutil.copyfile(self.template, self.dir / "kairos.db")
        self.env = make_env(make_engine(self.dir / "kairos.db"))

    def teardown(self) -> None:
        self.env.engine.dispose()
        shutil.rmtree(self.dir, ignore_errors=True)

    @initialize()
    def one_task_from_idea_to_done(self) -> None:
        """Every example starts with a finished task, so the walk always has somewhere to go."""
        for _ in range(12):
            self._advance("t1", approve=True, via_move=False)

    # --- random moves: anyone may try anything ----------------------------------------------

    @rule(actor=st.sampled_from(ACTORS), tid=st.sampled_from(TASK_IDS))
    def create(self, actor: Actor, tid: str) -> None:
        draft = Task(
            id=tid,
            title="T",
            type="bug",
            project_id="p1",
            created_by=actor.id,
            description="Something",
            subtasks=(Subtask("s1", "Step"),),
        )
        self.env.service.create_task(actor, draft)

    @rule(
        actor=st.sampled_from(ACTORS),
        tid=st.sampled_from(TASK_IDS),
        to=st.sampled_from(list(Status)),
        reason=st.sampled_from([None, "because"]),
        override=st.sampled_from([None, "urgent"]),
    )
    def move(
        self, actor: Actor, tid: str, to: Status, reason: str | None, override: str | None
    ) -> None:
        self.env.service.move_task(actor, tid, to, reason=reason, override_reason=override)

    @rule(
        actor=st.sampled_from(ACTORS),
        tid=st.sampled_from(TASK_IDS),
        agent=st.sampled_from(["a1", "a2", "o1", "ghost"]),
    )
    def assign(self, actor: Actor, tid: str, agent: str) -> None:
        self.env.service.assign_task(actor, tid, agent)

    @rule(actor=st.sampled_from(ACTORS), tid=st.sampled_from(TASK_IDS))
    def unassign(self, actor: Actor, tid: str) -> None:
        self.env.service.unassign_task(actor, tid, "reassigning")

    @rule(
        actor=st.sampled_from(ACTORS),
        tid=st.sampled_from(TASK_IDS),
        changes=st.sampled_from(CHANGES),
    )
    def update(self, actor: Actor, tid: str, changes: dict[str, object]) -> None:
        self.env.service.update_fields(actor, tid, changes)

    @rule(actor=st.sampled_from(ACTORS), tid=st.sampled_from(TASK_IDS))
    def evidence(self, actor: Actor, tid: str) -> None:
        self.env.service.attach_evidence(actor, tid, "c1", PROOF)

    @rule(
        actor=st.sampled_from(ACTORS),
        tid=st.sampled_from(TASK_IDS),
        blocker=st.sampled_from(TASK_IDS),
        add=st.booleans(),
    )
    def dependency(self, actor: Actor, tid: str, blocker: str, add: bool) -> None:
        if add:
            self.env.service.add_dependency(actor, tid, blocker)
        else:
            self.env.service.remove_dependency(actor, tid, blocker)

    @rule(
        actor=st.sampled_from(ACTORS),
        tid=st.sampled_from(TASK_IDS),
        to=st.sampled_from(list(SubtaskStatus)),
    )
    def subtask(self, actor: Actor, tid: str, to: SubtaskStatus) -> None:
        self.env.service.move_subtask(actor, tid, "s1", to, reason="because")

    @rule(actor=st.sampled_from(ACTORS), tid=st.sampled_from(TASK_IDS))
    def cancellation(self, actor: Actor, tid: str) -> None:
        self.env.service.request_cancellation(actor, tid, "not needed")

    @rule(
        actor=st.sampled_from(ACTORS),
        tid=st.sampled_from(TASK_IDS),
        approve=st.booleans(),
    )
    def resolve(self, actor: Actor, tid: str, approve: bool) -> None:
        self.env.service.resolve_request(actor, tid, approve, "because")

    # --- guided progress, so the walk reaches the interesting statuses ----------------------

    @rule(
        tid=st.sampled_from(TASK_IDS),
        approve=st.booleans(),
        via_move=st.booleans(),
        steps=st.integers(min_value=1, max_value=8),
    )
    def drive(self, tid: str, approve: bool, via_move: bool, steps: int) -> None:
        for _ in range(steps):
            self._advance(tid, approve, via_move)

    def _advance(self, tid: str, approve: bool, via_move: bool) -> None:
        """One plausible next step for the task, then note where it stands."""
        self._step(tid, approve, via_move)
        task = self.env.task(tid)
        if task is not None:
            COVERAGE[task.status.value] += 1

    def _step(self, tid: str, approve: bool, via_move: bool) -> None:
        """One plausible next step for the task, whoever would take it."""
        env, service = self.env, self.env.service
        task = env.task(tid)
        if task is None:
            draft = Task(
                id=tid,
                title="T",
                type="bug",
                project_id="p1",
                created_by="owner",
                description="Something",
            )
            service.create_task(OWNER, draft)
            return
        carrier = Actor(ActorKind.AGENT, task.assignee) if task.assignee else None
        match task.status:
            case Status.PROPOSED:
                service.move_task(ORCH, tid, Status.BACKLOG)
            case Status.BACKLOG if not task.criteria:
                service.update_fields(OWNER, tid, {"criteria": (Criterion("c1", "It works"),)})
            case Status.BACKLOG:
                service.move_task(ORCH, tid, Status.READY)
            case Status.READY if carrier is None:
                service.assign_task(ORCH, tid, "a1" if tid != "t2" else "a2")
            case Status.READY if carrier is not None:
                service.move_task(carrier, tid, Status.IN_PROGRESS)
            case Status.IN_PROGRESS if carrier is not None:
                if any(not c.evidence for c in task.criteria):
                    service.attach_evidence(carrier, tid, "c1", PROOF)
                elif not task.delivery_summary:
                    service.update_fields(carrier, tid, {"delivery_summary": "Done"})
                else:
                    service.move_task(carrier, tid, Status.IN_REVIEW)
            case Status.IN_REVIEW if via_move:
                # The owner drags the card instead of using the approval queue.
                service.move_task(
                    OWNER, tid, Status.DONE if approve else Status.READY, reason="Redo"
                )
            case Status.IN_REVIEW:
                service.resolve_request(OWNER, tid, approve, "Please redo it")
            case _:
                pass

    # --- what must always hold --------------------------------------------------------------

    @invariant()
    def the_database_holds(self) -> None:
        env = self.env
        assert env.verify().ok, "the hash chain broke"
        tasks = env.queries.list_tasks(OWNER)
        for task in tasks:
            COVERAGE[task.status.value] += 1

        busy = Counter(t.assignee for t in tasks if t.status is Status.IN_PROGRESS)
        assert all(count == 1 for count in busy.values()), f"two in progress for one agent: {busy}"

        with env.engine.connect() as conn:
            pending = conn.exec_driver_sql(
                "SELECT task_id, count(*) FROM approval_requests WHERE state = 'pending'"
                " GROUP BY task_id"
            ).all()
        assert all(count == 1 for _, count in pending), "two pending requests for one task"

        # A delivery request is pending exactly while its task is in review, and a task that is
        # closed has no cancellation request left waiting.
        with env.engine.connect() as conn:
            kinds = conn.exec_driver_sql(
                "SELECT task_id, kind FROM approval_requests WHERE state = 'pending'"
            ).all()
        deliveries = {task_id for task_id, kind in kinds if kind == "delivery"}
        in_review = {t.id for t in tasks if t.status is Status.IN_REVIEW}
        assert deliveries == in_review, f"pending deliveries {deliveries} vs in review {in_review}"
        closed = {t.id for t in tasks if t.status in CLOSED}
        cancellations = {task_id for task_id, kind in kinds if kind == "cancellation"}
        assert not cancellations & closed, "a closed task still has a pending cancellation request"

        replayed: dict[str, tuple[Status, str | None]] = {}
        for event in env.events():
            if event.type is EventType.ITEM_CREATED:
                replayed[event.entity_id] = (Status(str(event.payload["status"])), None)
            elif event.type is EventType.STATUS_CHANGED:
                status = Status(str(event.payload["to"]))
                replayed[event.entity_id] = (status, replayed[event.entity_id][1])
                if status in CLOSED:
                    assert event.actor_kind is ActorKind.OWNER, f"{event.actor_kind} closed a task"
            elif event.type is EventType.ASSIGNED:
                replayed[event.entity_id] = (
                    replayed[event.entity_id][0],
                    str(event.payload["agent"]),
                )
            elif event.type is EventType.UNASSIGNED:
                replayed[event.entity_id] = (replayed[event.entity_id][0], None)
        assert {t.id: (t.status, t.assignee) for t in tasks} == replayed, "rows differ from events"


def test_the_database_invariants_hold_under_random_use(migrated_template: Path):
    Machine.template = migrated_template
    COVERAGE.clear()
    run_state_machine_as_test(
        Machine,
        settings=settings(
            max_examples=25,
            stateful_step_count=30,
            deadline=None,
            suppress_health_check=[
                HealthCheck.too_slow,
                HealthCheck.data_too_large,
                HealthCheck.filter_too_much,
            ],
            database=None,
        ),
    )
    # The walk must actually get places: a model that never starts a task proves nothing.
    for reached in ("backlog", "ready", "in_progress", "in_review", "done"):
        assert COVERAGE[reached] > 0, f"the walk never reached {reached}: {dict(COVERAGE)}"
