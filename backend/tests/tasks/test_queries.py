from collections.abc import Callable

from kairos.domain.actor import Actor, ActorKind
from kairos.domain.decision import Rejected, RejectionCode
from kairos.domain.events import EventType
from kairos.domain.model import ApprovalRequest, RequestKind, Task
from kairos.domain.status import Status

from .support import Env

OWNER = Actor(ActorKind.OWNER, "owner")
ORCH = Actor(ActorKind.ORCHESTRATOR, "o1")
A1 = Actor(ActorKind.AGENT, "a1")
A2 = Actor(ActorKind.AGENT, "a2")
SYSTEM = Actor(ActorKind.SYSTEM, "system")

MakeTask = Callable[..., Task]


def _board(env: Env, make_task: MakeTask) -> None:
    env.put(
        make_task(id="mine", status=Status.READY, assignee="a1"),
        make_task(id="theirs", status=Status.READY, assignee="a2"),
        make_task(id="loose", status=Status.BACKLOG),
        make_task(id="draft", status=Status.PROPOSED, created_by="a1"),
        make_task(id="taken", status=Status.PROPOSED, created_by="a1", assignee="a2"),
    )


def _ids(tasks: list[Task]) -> list[str]:
    return [t.id for t in tasks]


def test_each_actor_lists_only_what_it_may_see(env: Env, make_task: MakeTask):
    _board(env, make_task)
    everything = ["mine", "theirs", "loose", "draft", "taken"]
    assert _ids(env.queries.list_tasks(OWNER)) == everything
    assert _ids(env.queries.list_tasks(ORCH)) == everything
    assert _ids(env.queries.list_tasks(A1)) == ["mine", "draft"]
    assert _ids(env.queries.list_tasks(A2)) == ["theirs", "taken"]
    assert env.queries.list_tasks(SYSTEM) == []


def test_listing_filters_by_status_and_assignee(env: Env, make_task: MakeTask):
    _board(env, make_task)
    assert _ids(env.queries.list_tasks(OWNER, status=Status.READY)) == ["mine", "theirs"]
    assert _ids(env.queries.list_tasks(OWNER, assignee="a2")) == ["theirs", "taken"]
    assert _ids(env.queries.list_tasks(A1, status=Status.READY)) == ["mine"]
    assert (
        env.queries.list_tasks(A1, assignee="a2") == []
    )  # asking for another's work shows nothing


def test_a_task_nobody_may_see_looks_exactly_like_a_missing_one(env: Env, make_task: MakeTask):
    _board(env, make_task)
    hidden = env.queries.get_task(A1, "theirs")
    missing = env.queries.get_task(A1, "ghost")
    assert isinstance(hidden, Rejected) and isinstance(missing, Rejected)
    assert hidden == missing
    assert hidden.code is RejectionCode.NOT_FOUND
    visible = env.queries.get_task(A1, "mine")
    assert not isinstance(visible, Rejected) and visible.id == "mine"
    assert not isinstance(env.queries.get_task(OWNER, "theirs"), Rejected)


def test_only_the_owner_and_the_orchestrator_see_the_approval_queue(env: Env, make_task: MakeTask):
    env.put(make_task(id="t1", status=Status.IN_REVIEW, assignee="a1"))
    request = ApprovalRequest("t1", RequestKind.DELIVERY, "a1", "Ready")
    env.put_request(request)
    assert env.queries.pending_requests(OWNER) == [request]
    assert env.queries.pending_requests(ORCH) == [request]
    assert env.queries.pending_requests(A1) == []
    assert env.queries.pending_requests(SYSTEM) == []
    env.service.resolve_request(OWNER, "t1", True, None)
    assert env.queries.pending_requests(OWNER) == []


def test_history_is_shown_for_visible_tasks_only(env: Env, make_task: MakeTask):
    env.put(make_task(id="mine", status=Status.IN_PROGRESS, assignee="a1"), make_task(id="theirs"))
    env.service.comment(A1, "mine", "First")
    env.service.comment(OWNER, "mine", "Second")
    env.service.comment(OWNER, "theirs", "Elsewhere")
    history = env.queries.task_history(A1, "mine")
    assert not isinstance(history, Rejected)
    assert [(e.type, e.actor_id) for e in history] == [
        (EventType.COMMENT_ADDED, "a1"),
        (EventType.COMMENT_ADDED, "owner"),
    ]
    hidden = env.queries.task_history(A1, "theirs")
    assert isinstance(hidden, Rejected) and hidden.code is RejectionCode.NOT_FOUND
    assert not isinstance(env.queries.task_history(OWNER, "theirs"), Rejected)
