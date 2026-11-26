"""Property-based tests: the invariants of design §6 hold for any sequence of actions.

`KairosWorld` plays the role of the use cases of slice 2: it keeps a small world of tasks,
computes the context the domain needs, calls the real decision functions with random actors
and applies only what comes back `Allowed`. After every step the invariants are checked.
"""

from dataclasses import replace
from itertools import product
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from kairos.domain import graph
from kairos.domain.actor import Actor, ActorKind, AgentProfile
from kairos.domain.approval import decide_request_cancellation, decide_resolve_request
from kairos.domain.assignment import decide_assign, decide_unassign, queue_load
from kairos.domain.changes import (
    ASSIGNEE_FIELDS,
    decide_add_dependency,
    decide_attach_evidence,
    decide_create,
    decide_remove_dependency,
    decide_update_fields,
)
from kairos.domain.decision import Allowed, Rejected
from kairos.domain.gates import GateContext
from kairos.domain.model import (
    ApprovalRequest,
    Criterion,
    Evidence,
    EvidenceKind,
    Priority,
    RequestKind,
    RequestState,
    Task,
    TaskType,
    is_blank,
)
from kairos.domain.policy import decide_transition
from kairos.domain.status import CLOSED, Status, SubtaskStatus

OWNER = Actor(ActorKind.OWNER, "owner")
ORCH = Actor(ActorKind.ORCHESTRATOR, "o1")
A1 = Actor(ActorKind.AGENT, "a1")
A2 = Actor(ActorKind.AGENT, "a2")
SYSTEM = Actor(ActorKind.SYSTEM, "sys")
ACTORS = (OWNER, ORCH, A1, A2, SYSTEM)
NON_OWNERS = (ORCH, A1, A2, SYSTEM)
PROFILES = {
    "a1": AgentProfile("a1", ActorKind.AGENT, frozenset({"bug"}), frozenset({"p1"}), 2),
    "a2": AgentProfile(
        "a2", ActorKind.AGENT, frozenset({"bug", "feature"}), frozenset({"p1", "p2"}), 2
    ),
    "o1": AgentProfile(
        "o1", ActorKind.ORCHESTRATOR, frozenset({"bug", "feature"}), frozenset({"p1", "p2"}), 3
    ),
}
TASK_TYPE = TaskType("bug", frozenset())
PROOF = Evidence(EvidenceKind.TEXT, "ran it", "x")
IDS = tuple(f"t{n}" for n in range(6))
AGENT_IDS = ("a1", "a2")

# Everything a non-owner may ever do to the status of a task (design §6.3).
NON_OWNER_MOVES = frozenset(
    {
        (Status.PROPOSED, Status.BACKLOG),
        (Status.BACKLOG, Status.READY),
        (Status.READY, Status.IN_PROGRESS),
        (Status.IN_PROGRESS, Status.IN_REVIEW),
        (Status.IN_PROGRESS, Status.READY),
    }
)

UPDATES: tuple[dict[str, Any], ...] = (
    {"criteria": (Criterion("c1", "works"),)},
    {"delivery_summary": "Done and verified."},
    {"delivery_summary": ""},
    {"working_notes": "notes"},
    {"title": "Renamed"},
    {"priority": Priority.P0},
)


def _reachable_from_itself(blocked_by: dict[str, frozenset[str]], start: str) -> bool:
    seen: set[str] = set()
    pending = list(blocked_by.get(start, frozenset()))
    while pending:
        current = pending.pop()
        if current == start:
            return True
        if current not in seen:
            seen.add(current)
            pending.extend(blocked_by.get(current, frozenset()))
    return False


class KairosWorld(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.tasks: dict[str, Task] = {}
        self.requests: dict[tuple[str, RequestKind], ApprovalRequest] = {}

    # -- the context a use case would compute -----------------------------------------------

    def _statuses(self) -> dict[str, Status]:
        return {tid: task.status for tid, task in self.tasks.items()}

    def _gate_context(self, task: Task, actor: Actor) -> GateContext:
        carrier = actor.id if actor.kind is ActorKind.AGENT else task.assignee
        others = frozenset(
            t.id
            for t in self.tasks.values()
            if carrier is not None
            and t.assignee == carrier
            and t.status is Status.IN_PROGRESS
            and t.id != task.id
        )
        statuses = self._statuses()
        return GateContext(
            TASK_TYPE,
            graph.open_blockers(task, statuses),
            others,
            graph.cancelled_blockers(task, statuses),
        )

    @initialize()
    def seed(self) -> None:
        """Four tasks the owner created, so that deep states are reachable from step one."""
        for index, (type_, project) in enumerate(
            [("bug", "p1"), ("bug", "p1"), ("feature", "p2"), ("bug", "p2")]
        ):
            draft = Task(IDS[index], "Seed", type_, project, OWNER.id)
            decision = decide_create(OWNER, None, draft)
            assert isinstance(decision, Allowed)
            self.tasks[draft.id] = decision.task

    # -- single steps: call the real decision, check what must hold, apply what is allowed ---

    def _move(
        self, tid: str, to_status: Status, actor: Actor, reason: str | None, override: str | None
    ) -> bool:
        task = self.tasks.get(tid)
        if task is None:
            return False
        ctx = self._gate_context(task, actor)
        decision = decide_transition(
            task, actor, to_status, ctx, reason=reason, override_reason=override
        )
        if not isinstance(decision, Allowed):
            return False
        if actor.kind is not ActorKind.OWNER:
            # Review Focus 1: only these moves are open to anybody but the owner.
            assert (task.status, to_status) in NON_OWNER_MOVES
            assert task.status not in CLOSED and to_status not in CLOSED
        if to_status is Status.IN_PROGRESS:
            assert not ctx.other_in_progress, "a second task went in progress for one agent"
            if actor.kind is ActorKind.AGENT:
                assert task.assignee == actor.id
        if to_status is Status.IN_REVIEW and actor.kind is ActorKind.AGENT:
            assert task.criteria and all(c.evidence for c in task.criteria)
            assert not is_blank(task.delivery_summary)
            assert not ctx.open_blockers
            assert SubtaskStatus.PENDING not in task.subtasks
        self.tasks[tid] = decision.task
        if decision.request is not None:
            self.requests[(tid, decision.request.kind)] = decision.request
        return True

    def _assign(self, tid: str, agent: str, actor: Actor) -> bool:
        task = self.tasks.get(tid)
        if task is None:
            return False
        profile = PROFILES[agent]
        load = queue_load(self.tasks.values(), agent)
        decision = decide_assign(task, actor, profile, load)
        if not isinstance(decision, Allowed):
            return False
        assert actor.kind in (ActorKind.OWNER, ActorKind.ORCHESTRATOR)
        assert load < profile.queue_limit
        assert task.type in profile.allowed_task_types
        assert task.project_id in profile.allowed_project_ids
        assert task.status is Status.READY and task.assignee is None
        self.tasks[tid] = decision.task
        return True

    def _update(self, tid: str, actor: Actor, change: dict[str, Any]) -> bool:
        task = self.tasks.get(tid)
        if task is None:
            return False
        decision = decide_update_fields(task, actor, change)
        if not isinstance(decision, Allowed):
            return False
        if actor.kind is ActorKind.AGENT and task.status is not Status.PROPOSED:
            assert set(change) <= ASSIGNEE_FIELDS, "an agent edited a triaged task"
        self.tasks[tid] = decision.task
        return True

    def _evidence(self, tid: str, actor: Actor) -> bool:
        task = self.tasks.get(tid)
        if task is None:
            return False
        decision = decide_attach_evidence(task, actor, "c1", PROOF)
        if not isinstance(decision, Allowed):
            return False
        assert actor.kind in (ActorKind.OWNER, ActorKind.AGENT)
        self.tasks[tid] = decision.task
        return True

    # -- random actions ---------------------------------------------------------------------

    @rule(
        actor=st.sampled_from(ACTORS),
        type_=st.sampled_from(["bug", "feature"]),
        project=st.sampled_from(["p1", "p2"]),
        with_criterion=st.booleans(),
    )
    def create(self, actor: Actor, type_: str, project: str, with_criterion: bool) -> None:
        if len(self.tasks) >= len(IDS):
            return
        criteria = (Criterion("c1", "works"),) if with_criterion else ()
        draft = Task(IDS[len(self.tasks)], "Title", type_, project, actor.id, criteria=criteria)
        decision = decide_create(actor, PROFILES.get(actor.id), draft)
        if isinstance(decision, Allowed):
            if actor.kind is not ActorKind.OWNER:
                assert decision.task.status is Status.PROPOSED
            self.tasks[decision.task.id] = decision.task

    @rule(
        tid=st.sampled_from(IDS),
        to_status=st.sampled_from(list(Status)),
        actor=st.sampled_from(ACTORS),
        reason=st.sampled_from([None, "", "because"]),
        override=st.sampled_from([None, "", "I decided"]),
    )
    def transition(
        self, tid: str, to_status: Status, actor: Actor, reason: str | None, override: str | None
    ) -> None:
        self._move(tid, to_status, actor, reason, override)

    @rule(
        tid=st.sampled_from(IDS),
        agent=st.sampled_from(list(PROFILES)),
        actor=st.sampled_from(ACTORS),
    )
    def assign(self, tid: str, agent: str, actor: Actor) -> None:
        self._assign(tid, agent, actor)

    @rule(tid=st.sampled_from(IDS), actor=st.sampled_from(ACTORS))
    def unassign(self, tid: str, actor: Actor) -> None:
        task = self.tasks.get(tid)
        if task is not None:
            decision = decide_unassign(task, actor, "freeing the slot")
            if isinstance(decision, Allowed):
                self.tasks[tid] = decision.task

    @rule(tid=st.sampled_from(IDS), actor=st.sampled_from(ACTORS), change=st.sampled_from(UPDATES))
    def update_fields(self, tid: str, actor: Actor, change: dict[str, Any]) -> None:
        self._update(tid, actor, change)

    @rule(tid=st.sampled_from(IDS), actor=st.sampled_from(ACTORS))
    def attach_evidence(self, tid: str, actor: Actor) -> None:
        self._evidence(tid, actor)

    @rule(tid=st.sampled_from(IDS), blocker=st.sampled_from(IDS), actor=st.sampled_from(ACTORS))
    def add_dependency(self, tid: str, blocker: str, actor: Actor) -> None:
        task = self.tasks.get(tid)
        if task is not None:
            known = {i: t.blocked_by for i, t in self.tasks.items()}
            decision = decide_add_dependency(task, actor, blocker, known)
            if isinstance(decision, Allowed):
                assert actor.kind in (ActorKind.OWNER, ActorKind.ORCHESTRATOR)
                self.tasks[tid] = decision.task

    @rule(tid=st.sampled_from(IDS), blocker=st.sampled_from(IDS), actor=st.sampled_from(ACTORS))
    def remove_dependency(self, tid: str, blocker: str, actor: Actor) -> None:
        task = self.tasks.get(tid)
        if task is not None:
            decision = decide_remove_dependency(task, actor, blocker)
            if isinstance(decision, Allowed):
                self.tasks[tid] = decision.task

    @rule(tid=st.sampled_from(IDS), actor=st.sampled_from(ACTORS))
    def request_cancellation(self, tid: str, actor: Actor) -> None:
        task = self.tasks.get(tid)
        if task is None:
            return
        pending = self.requests.get((tid, RequestKind.CANCELLATION))
        exists = pending is not None and pending.state is RequestState.PENDING
        decision = decide_request_cancellation(task, actor, "no longer needed", exists)
        if isinstance(decision, Allowed) and decision.request is not None:
            assert actor.kind is ActorKind.AGENT and task.assignee == actor.id
            self.requests[(tid, RequestKind.CANCELLATION)] = decision.request

    @rule(
        tid=st.sampled_from(IDS),
        kind=st.sampled_from(list(RequestKind)),
        actor=st.sampled_from(ACTORS),
        approve=st.booleans(),
    )
    def resolve_request(self, tid: str, kind: RequestKind, actor: Actor, approve: bool) -> None:
        task, request = self.tasks.get(tid), self.requests.get((tid, kind))
        if task is None or request is None:
            return
        ctx = self._gate_context(task, actor)
        decision = decide_resolve_request(task, request, actor, approve, "noted", ctx)
        if isinstance(decision, Allowed):
            assert actor.kind is ActorKind.OWNER
            self.tasks[tid] = decision.task
            if decision.request is not None:
                self.requests[(tid, kind)] = decision.request

    # -- macro actions: sequences of the same real decisions, to reach deep states ------------
    # Random steps rarely line up "a ready task, assigned, started, delivered"; these do,
    # without shortcuts: every step still goes through the domain and may be rejected.

    def _ready_and_assign(self, tid: str, agent: str) -> None:
        self._update(tid, OWNER, UPDATES[0])
        self._move(tid, Status.BACKLOG, OWNER, None, None)
        self._move(tid, Status.READY, OWNER, None, None)
        self._assign(tid, agent, OWNER)

    def _start(self, tid: str) -> None:
        task = self.tasks.get(tid)
        if task is not None and task.assignee in AGENT_IDS:
            self._move(tid, Status.IN_PROGRESS, Actor(ActorKind.AGENT, task.assignee), None, None)

    def _finish(self, tid: str) -> None:
        task = self.tasks.get(tid)
        if task is not None and task.assignee in AGENT_IDS:
            agent = Actor(ActorKind.AGENT, task.assignee)
            self._evidence(tid, agent)
            self._update(tid, agent, UPDATES[1])
            self._move(tid, Status.IN_REVIEW, agent, None, None)

    @rule(tid=st.sampled_from(IDS), agent=st.sampled_from(list(PROFILES)))
    def owner_readies_and_assigns(self, tid: str, agent: str) -> None:
        self._ready_and_assign(tid, agent)

    @rule(tid=st.sampled_from(IDS), agent=st.sampled_from(list(PROFILES)))
    def owner_readies_assigns_and_agent_starts(self, tid: str, agent: str) -> None:
        self._ready_and_assign(tid, agent)
        self._start(tid)

    @rule(tid=st.sampled_from(IDS), agent=st.sampled_from(list(PROFILES)))
    def agent_delivers(self, tid: str, agent: str) -> None:
        self._ready_and_assign(tid, agent)
        self._start(tid)
        self._finish(tid)

    @rule(
        tid=st.sampled_from(IDS),
        agent=st.sampled_from(list(PROFILES)),
        back_to=st.sampled_from([Status.PROPOSED, Status.BACKLOG, Status.READY]),
    )
    def owner_demotes_an_assigned_task(self, tid: str, agent: str, back_to: Status) -> None:
        self._ready_and_assign(tid, agent)
        self._move(tid, back_to, OWNER, "changed my mind", None)

    @rule(tid=st.sampled_from(IDS), agent=st.sampled_from(list(PROFILES)))
    def agent_submits_without_evidence(self, tid: str, agent: str) -> None:
        self._ready_and_assign(tid, agent)
        self._start(tid)
        task = self.tasks.get(tid)
        if task is not None and task.assignee in AGENT_IDS:
            actor = Actor(ActorKind.AGENT, task.assignee)
            self._update(tid, actor, UPDATES[1])  # a summary, but no evidence
            self._move(tid, Status.IN_REVIEW, actor, None, "please")

    # -- invariants, checked after every step -----------------------------------------------

    @invariant()
    def at_most_one_task_in_progress_per_agent(self) -> None:
        for agent in PROFILES:
            running = [
                t
                for t in self.tasks.values()
                if t.assignee == agent and t.status is Status.IN_PROGRESS
            ]
            assert len(running) <= 1, f"{agent} has {len(running)} tasks in progress"

    @invariant()
    def dependencies_are_acyclic(self) -> None:
        edges = {tid: task.blocked_by for tid, task in self.tasks.items()}
        for tid in edges:
            assert not _reachable_from_itself(edges, tid), f"{tid} blocks itself"

    @invariant()
    def only_working_statuses_hold_an_assignment(self) -> None:
        keeps = {Status.READY, Status.IN_PROGRESS, Status.IN_REVIEW, Status.DONE}
        for task in self.tasks.values():
            assert task.assignee is None or task.status in keeps, (task.id, task.status)


KairosWorld.TestCase.settings = settings(max_examples=80, stateful_step_count=40, deadline=None)
TestKairosWorld = KairosWorld.TestCase


# -- pure properties over arbitrary inputs ------------------------------------------------------

_criterion = st.builds(
    Criterion,
    id=st.just("c1"),
    text=st.just("x"),
    evidence=st.lists(st.just(PROOF), max_size=1).map(tuple),
)
_task = st.builds(
    Task,
    id=st.just("t1"),
    title=st.just("T"),
    type=st.sampled_from(["bug", "feature"]),
    project_id=st.sampled_from(["p1", "p2"]),
    created_by=st.sampled_from(["owner", "a1", "a2"]),
    status=st.sampled_from(list(Status)),
    assignee=st.sampled_from([None, "a1", "a2"]),
    criteria=st.lists(_criterion, max_size=2).map(tuple),
    subtasks=st.lists(st.sampled_from(list(SubtaskStatus)), max_size=2).map(tuple),
    delivery_summary=st.sampled_from(["", "   ", "ok"]),
)
_ctx = st.builds(
    GateContext,
    task_type=st.just(TASK_TYPE),
    open_blockers=st.sets(st.sampled_from(["x", "y"])).map(frozenset),
    other_in_progress=st.sets(st.sampled_from(["u", "v"])).map(frozenset),
    cancelled_blockers=st.sets(st.sampled_from(["c"])).map(frozenset),
)
_text = st.none() | st.text(max_size=6)


@settings(max_examples=150, deadline=None)
@given(task=_task, ctx=_ctx, reason=_text, override=_text)
def test_non_owner_never_closes_deletes_or_moves_backwards(
    task: Task, ctx: GateContext, reason: str | None, override: str | None
) -> None:
    # Every (status, non-owner actor, target) triple is tried for each generated task.
    for status, actor, target in product(Status, NON_OWNERS, Status):
        current = replace(task, status=status)
        decision = decide_transition(
            current, actor, target, ctx, reason=reason, override_reason=override
        )
        if isinstance(decision, Allowed):
            assert (status, target) in NON_OWNER_MOVES, (status, actor.kind, target)
            assert decision.task.status not in CLOSED


@settings(max_examples=150, deadline=None)
@given(task=_task, ctx=_ctx, override=_text)
def test_a_busy_agent_never_gets_a_second_task_in_progress(
    task: Task, ctx: GateContext, override: str | None
) -> None:
    busy = GateContext(ctx.task_type, frozenset(), frozenset({"other"}), ctx.cancelled_blockers)
    for status, actor in product(Status, ACTORS):
        current = replace(task, status=status)
        decision = decide_transition(
            current, actor, Status.IN_PROGRESS, busy, override_reason=override
        )
        if actor.kind is ActorKind.AGENT or current.assignee is not None:
            assert not isinstance(decision, Allowed), (status, actor.kind)


@settings(max_examples=300, deadline=None)
@given(
    task=_task,
    actor=st.sampled_from(ACTORS),
    target=st.sampled_from(list(Status)),
    ctx=_ctx,
    reason=_text,
    override=_text,
    load=st.integers(min_value=-1, max_value=10),
)
def test_every_decision_is_allowed_or_rejected(
    task: Task,
    actor: Actor,
    target: Status,
    ctx: GateContext,
    reason: str | None,
    override: str | None,
    load: int,
) -> None:
    moved = decide_transition(task, actor, target, ctx, reason=reason, override_reason=override)
    assigned = decide_assign(task, actor, PROFILES["a1"], load)
    unassigned = decide_unassign(task, actor, reason)
    for decision in (moved, assigned, unassigned):
        assert isinstance(decision, (Allowed, Rejected))
        if isinstance(decision, Allowed):
            assert decision.events
