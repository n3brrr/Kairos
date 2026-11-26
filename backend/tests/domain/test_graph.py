from kairos.domain.graph import (
    cancelled_blockers,
    is_blocked,
    open_blockers,
    would_create_cycle,
)
from kairos.domain.model import Task
from kairos.domain.status import Status


def _task(blocked_by: frozenset[str] = frozenset()) -> Task:
    return Task(
        id="t", title="T", type="bug", project_id="p", created_by="a", blocked_by=blocked_by
    )


def test_self_dependency_is_a_cycle():
    assert would_create_cycle({}, "a", "a")


def test_two_step_cycle():
    # B is blocked by A; making A blocked by B closes the loop.
    assert would_create_cycle({"B": frozenset({"A"})}, blocker_id="B", blocked_id="A")


def test_long_cycle():
    chain = {"C": frozenset({"B"}), "B": frozenset({"A"})}
    assert would_create_cycle(chain, blocker_id="C", blocked_id="A")


def test_diamond_is_not_a_cycle():
    diamond = {"B": frozenset({"A"}), "C": frozenset({"A"}), "D": frozenset({"B", "C"})}
    assert not would_create_cycle(diamond, blocker_id="A", blocked_id="D")


def test_unrelated_dependency_is_not_a_cycle():
    assert not would_create_cycle({"B": frozenset({"A"})}, blocker_id="X", blocked_id="B")


def test_done_and_cancelled_blockers_are_resolved():
    statuses = {"d": Status.DONE, "c": Status.CANCELLED, "o": Status.IN_PROGRESS}
    task = _task(frozenset({"d", "c", "o"}))
    assert open_blockers(task, statuses) == frozenset({"o"})
    assert is_blocked(task, statuses)
    assert not is_blocked(_task(frozenset({"d", "c"})), statuses)


def test_missing_blocker_counts_as_open():
    assert open_blockers(_task(frozenset({"ghost"})), {}) == frozenset({"ghost"})


def test_cancelled_blockers_are_listed():
    statuses = {"d": Status.DONE, "c": Status.CANCELLED}
    assert cancelled_blockers(_task(frozenset({"d", "c"})), statuses) == frozenset({"c"})
