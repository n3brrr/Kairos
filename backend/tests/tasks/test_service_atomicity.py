"""A decision is persisted whole or not at all, and a rejection leaves no trace."""

import threading
from collections.abc import Callable
from typing import Any

import pytest

from kairos.domain.actor import Actor, ActorKind
from kairos.domain.decision import Decision, Rejected, RejectionCode
from kairos.domain.model import (
    ApprovalRequest,
    Criterion,
    Evidence,
    EvidenceKind,
    RequestKind,
    Subtask,
    Task,
)
from kairos.domain.status import Status, SubtaskStatus
from kairos.features.tasks import service as service_module
from kairos.features.tasks.repository import TaskRepository

from .support import Env

OWNER = Actor(ActorKind.OWNER, "owner")
ORCH = Actor(ActorKind.ORCHESTRATOR, "o1")
A1 = Actor(ActorKind.AGENT, "a1")
A2 = Actor(ActorKind.AGENT, "a2")
PROOF = Evidence(EvidenceKind.TEXT, "ok", "a1")

MakeTask = Callable[..., Task]


def _in_review(make_task: MakeTask) -> Task:
    return make_task(
        status=Status.IN_REVIEW,
        assignee="a1",
        criteria=(Criterion("c1", "works", (PROOF,)),),
        delivery_summary="Done",
        subtasks=(Subtask("s1", "A", SubtaskStatus.IN_REVIEW),),
    )


# Calls that must be rejected, against a task in review carried by a1.
REJECTED_CALLS: dict[str, tuple[Callable[[Env], Decision], RejectionCode]] = {
    "agent approves": (
        lambda e: e.service.resolve_request(A1, "t1", True, None),
        RejectionCode.NOT_PERMITTED,
    ),
    "orchestrator approves": (
        lambda e: e.service.resolve_request(ORCH, "t1", True, None),
        RejectionCode.NOT_PERMITTED,
    ),
    "agent moves to done": (
        lambda e: e.service.move_task(A1, "t1", Status.DONE),
        RejectionCode.NOT_PERMITTED,
    ),
    "orchestrator cancels": (
        lambda e: e.service.move_task(ORCH, "t1", Status.CANCELLED),
        RejectionCode.NOT_PERMITTED,
    ),
    "agent cancels": (
        lambda e: e.service.move_task(A1, "t1", Status.CANCELLED),
        RejectionCode.NOT_PERMITTED,
    ),
    "agent edits the title": (
        lambda e: e.service.update_fields(A1, "t1", {"title": "x"}),
        RejectionCode.NOT_PERMITTED,
    ),
    "unknown subtask": (
        lambda e: e.service.move_subtask(OWNER, "t1", "ghost", SubtaskStatus.DONE),
        RejectionCode.UNKNOWN_SUBTASK,
    ),
    "agent approves a subtask": (
        lambda e: e.service.move_subtask(A1, "t1", "s1", SubtaskStatus.DONE),
        RejectionCode.WRONG_STATUS,
    ),
    "blank comment": (lambda e: e.service.comment(OWNER, "t1", " "), RejectionCode.EMPTY_TEXT),
    "stranger acts": (lambda e: e.service.comment(A2, "t1", "hi"), RejectionCode.NOT_FOUND),
}


@pytest.mark.parametrize("name", list(REJECTED_CALLS))
def test_a_rejected_call_leaves_every_table_untouched(env: Env, make_task: MakeTask, name: str):
    env.put(_in_review(make_task))
    env.put_request(ApprovalRequest("t1", RequestKind.DELIVERY, "a1", "Done"))
    before = env.snapshot()
    call, code = REJECTED_CALLS[name]
    result = call(env)
    assert isinstance(result, Rejected), result
    assert result.code is code
    assert env.snapshot() == before


def test_a_failure_while_logging_rolls_the_task_back_too(
    env: Env, make_task: MakeTask, monkeypatch: pytest.MonkeyPatch
):
    env.put(make_task(status=Status.READY))
    before = env.snapshot()

    def boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("the log is down")

    monkeypatch.setattr(service_module, "append_events", boom)
    with pytest.raises(RuntimeError, match="the log is down"):
        env.service.assign_task(OWNER, "t1", "a1")
    assert env.snapshot() == before
    task = env.task("t1")
    assert task is not None and task.assignee is None


def test_the_database_guard_is_translated_when_the_domain_read_was_stale(
    env: Env, make_task: MakeTask, monkeypatch: pytest.MonkeyPatch
):
    env.put(
        make_task(id="t1", status=Status.IN_PROGRESS, assignee="a1"),
        make_task(id="t2", status=Status.READY, assignee="a1"),
    )

    # The domain is told nobody else is in progress, so only the unique index can object.
    def stale(_self: TaskRepository, _agent: str, *, excluding: str) -> frozenset[str]:
        return frozenset()

    monkeypatch.setattr(TaskRepository, "other_in_progress", stale)
    before = env.snapshot()
    result = env.service.move_task(A1, "t2", Status.IN_PROGRESS)
    assert isinstance(result, Rejected) and result.code is RejectionCode.GATE_FAILED
    assert [g.code.value for g in result.gates] == ["agent_busy"]
    assert env.snapshot() == before


def test_two_agents_racing_for_the_same_agent_slot_one_wins(env: Env, make_task: MakeTask):
    env.put(
        make_task(id="t1", status=Status.READY, assignee="a1"),
        make_task(id="t2", status=Status.READY, assignee="a1"),
    )
    barrier = threading.Barrier(2)
    results: dict[str, Decision] = {}

    def start(task_id: str) -> None:
        barrier.wait()
        results[task_id] = env.service.move_task(A1, task_id, Status.IN_PROGRESS)

    threads = [threading.Thread(target=start, args=(name,)) for name in ("t1", "t2")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    outcomes = sorted(type(result).__name__ for result in results.values())
    assert outcomes == ["Allowed", "Rejected"]
    in_progress = [
        t for t in (env.task("t1"), env.task("t2")) if t and t.status is Status.IN_PROGRESS
    ]
    assert len(in_progress) == 1
    assert env.verify().ok
