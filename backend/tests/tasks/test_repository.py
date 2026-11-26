from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from kairos.adapters.db.engine import make_engine
from kairos.adapters.db.migrate import upgrade
from kairos.domain.actor import ActorKind, AgentProfile
from kairos.domain.model import (
    ApprovalRequest,
    Criterion,
    Evidence,
    EvidenceKind,
    Priority,
    RequestKind,
    RequestState,
    Subtask,
    Task,
)
from kairos.domain.registry import Epic, Project
from kairos.domain.status import Status, SubtaskStatus
from kairos.features.registry.repository import RegistryRepository
from kairos.features.tasks.repository import Comment, TaskRepository

PROFILE_A1 = AgentProfile("a1", ActorKind.AGENT, frozenset({"bug", "feature"}), frozenset({"p1"}))
PROFILE_A2 = AgentProfile("a2", ActorKind.AGENT, frozenset(), frozenset(), queue_limit=1)

Repos = tuple[TaskRepository, RegistryRepository]


def make_task(**changes: object) -> Task:
    base = Task(id="t1", title="T", type="bug", project_id="p1", created_by="owner")
    return replace(base, **changes)  # type: ignore[arg-type]


def _seed(conn: Connection) -> Repos:
    registry = RegistryRepository(conn)
    registry.save_agent(PROFILE_A1)
    registry.save_agent(PROFILE_A2)
    registry.save_project(Project("p1", "Kairos", "Development"))
    registry.save_epic(Epic("e1", "p1", "Epic"))
    tasks = TaskRepository(conn)
    tasks.save(make_task(id="b1"))
    tasks.save(make_task(id="b2"))
    return tasks, registry


@pytest.fixture
def repos(conn: Connection) -> Repos:
    return _seed(conn)


# --- round trip -------------------------------------------------------------------------------

_text = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=12)
_nonblank = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Nd")), min_size=1, max_size=6
)
_evidence = st.builds(
    Evidence, kind=st.sampled_from(list(EvidenceKind)), content=_text, added_by=_nonblank
)
_criterion = st.builds(
    Criterion,
    id=_nonblank,
    text=_text,
    evidence=st.lists(_evidence, max_size=2).map(tuple),
)
_subtask = st.builds(
    Subtask, id=_nonblank, title=_text, status=st.sampled_from(list(SubtaskStatus))
)
_dates = st.dates(min_value=date(2000, 1, 1), max_value=date(2100, 1, 1))
_tasks = st.builds(
    Task,
    id=st.just("t1"),
    title=_text,
    type=st.sampled_from(["bug", "feature", "chore"]),
    project_id=st.just("p1"),
    created_by=_nonblank,
    parent_id=st.sampled_from([None, "e1"]),
    status=st.sampled_from(list(Status)),
    priority=st.sampled_from(list(Priority)),
    description=_text,
    labels=st.lists(_text, max_size=3).map(tuple),
    start_date=st.none() | _dates,
    due_date=st.none() | _dates,
    recurrence=st.none() | _text,
    criteria=st.lists(_criterion, max_size=3, unique_by=lambda c: c.id).map(tuple),
    subtasks=st.lists(_subtask, max_size=3, unique_by=lambda s: s.id).map(tuple),
    blocked_by=st.sets(st.sampled_from(["b1", "b2"])).map(frozenset),
    assignee=st.sampled_from([None, "a1", "a2"]),
    delivery_summary=_text,
    working_notes=_text,
)


@settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(task=_tasks)
def test_a_saved_task_comes_back_equal(task: Task):
    engine = make_engine(None)
    upgrade(engine)
    with engine.begin() as conn:
        tasks, _ = _seed(conn)
        tasks.save(task)
        assert tasks.get("t1") == task
    engine.dispose()


def test_saving_twice_does_not_duplicate_children(repos: Repos):
    tasks, _ = repos
    proof = Evidence(EvidenceKind.TEXT, "ok", "a1")
    task = make_task(
        criteria=(Criterion("c1", "works", (proof, proof)),),
        subtasks=(Subtask("s1", "Step"),),
        blocked_by=frozenset({"b1"}),
    )
    tasks.save(task)
    tasks.save(task)
    assert tasks.get("t1") == task


def test_saving_a_changed_task_replaces_its_children(repos: Repos):
    tasks, _ = repos
    tasks.save(
        make_task(
            criteria=(Criterion("c1", "a"), Criterion("c2", "b")),
            subtasks=(Subtask("s1", "x"), Subtask("s2", "y")),
            blocked_by=frozenset({"b1", "b2"}),
        )
    )
    changed = make_task(
        criteria=(Criterion("c2", "b"),),
        subtasks=(Subtask("s2", "y", SubtaskStatus.DONE),),
        blocked_by=frozenset({"b2"}),
        status=Status.BACKLOG,
    )
    tasks.save(changed)
    assert tasks.get("t1") == changed


def test_two_tasks_may_use_the_same_subtask_and_criterion_ids(repos: Repos):
    tasks, _ = repos
    one = make_task(id="t1", subtasks=(Subtask("s1", "a"),), criteria=(Criterion("c1", "a"),))
    two = make_task(id="t2", subtasks=(Subtask("s1", "b"),), criteria=(Criterion("c1", "b"),))
    tasks.save(one)
    tasks.save(two)
    assert tasks.get("t1") == one
    assert tasks.get("t2") == two


def test_a_missing_task_is_none_and_a_project_is_not_a_task(repos: Repos):
    tasks, _ = repos
    assert tasks.get("nope") is None
    assert tasks.get("p1") is None
    assert tasks.get("e1") is None


def test_a_task_in_an_unknown_project_is_refused(repos: Repos):
    tasks, _ = repos
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        tasks.save(make_task(project_id="missing"))


# --- what the gates and the queue need --------------------------------------------------------


def test_blocked_by_map_lists_every_task_even_without_blockers(repos: Repos):
    tasks, _ = repos
    tasks.save(make_task(id="t1", blocked_by=frozenset({"b1", "b2"})))
    assert tasks.blocked_by_map() == {
        "b1": frozenset(),
        "b2": frozenset(),
        "t1": frozenset({"b1", "b2"}),
    }


def test_statuses_returns_the_known_ids_only(repos: Repos):
    tasks, _ = repos
    tasks.save(make_task(id="b1", status=Status.DONE))
    assert tasks.statuses(["b1", "b2", "ghost"]) == {"b1": Status.DONE, "b2": Status.PROPOSED}
    assert tasks.statuses([]) == {}


def test_other_in_progress_excludes_the_given_task_and_other_agents(repos: Repos):
    tasks, _ = repos
    tasks.save(make_task(id="t1", status=Status.IN_PROGRESS, assignee="a1"))
    tasks.save(make_task(id="t2", status=Status.IN_PROGRESS, assignee="a2"))
    tasks.save(make_task(id="t3", status=Status.READY, assignee="a1"))
    assert tasks.other_in_progress("a1", excluding="t3") == frozenset({"t1"})
    assert tasks.other_in_progress("a1", excluding="t1") == frozenset()
    assert tasks.other_in_progress("a2", excluding="t1") == frozenset({"t2"})


def test_queue_load_counts_ready_and_in_progress_but_not_review(repos: Repos):
    tasks, _ = repos
    tasks.save(make_task(id="t1", status=Status.READY, assignee="a1"))
    tasks.save(make_task(id="t2", status=Status.IN_PROGRESS, assignee="a1"))
    tasks.save(make_task(id="t3", status=Status.IN_REVIEW, assignee="a1"))
    tasks.save(make_task(id="t4", status=Status.DONE, assignee="a1"))
    tasks.save(make_task(id="t5", status=Status.READY, assignee="a2"))
    assert tasks.load("a1") == 2
    assert tasks.load("a2") == 1
    assert tasks.load("nobody") == 0


def test_list_filters_by_status_and_assignee_in_insertion_order(repos: Repos):
    tasks, _ = repos
    tasks.save(make_task(id="t1", status=Status.READY, assignee="a1"))
    tasks.save(make_task(id="t2", status=Status.READY))
    tasks.save(make_task(id="t3", status=Status.BACKLOG, assignee="a1"))
    tasks.save(make_task(id="t1", status=Status.READY, assignee="a1", title="again"))

    def ids(found: list[Task]) -> list[str]:
        return [t.id for t in found]

    assert ids(tasks.list_tasks()) == ["b1", "b2", "t1", "t2", "t3"]
    assert ids(tasks.list_tasks(status=Status.READY)) == ["t1", "t2"]
    assert ids(tasks.list_tasks(assignee="a1")) == ["t1", "t3"]
    assert ids(tasks.list_tasks(status=Status.READY, assignee="a1")) == ["t1"]


def test_a_task_type_comes_back_with_its_required_fields(repos: Repos):
    tasks, _ = repos
    feature = tasks.get_task_type("feature")
    assert feature is not None
    assert feature.required_fields == frozenset({"description", "priority"})
    assert feature.criteria_template == ()
    assert tasks.get_task_type("nope") is None


# --- approval requests and comments -----------------------------------------------------------


def test_a_pending_request_is_saved_and_then_resolved_in_place(repos: Repos):
    tasks, _ = repos
    tasks.save(make_task(id="t1"))
    assert tasks.get_pending_request("t1") is None
    request = ApprovalRequest("t1", RequestKind.DELIVERY, "a1", "ready for review")
    tasks.save_request(request)
    assert tasks.get_pending_request("t1") == request
    resolved = replace(request, state=RequestState.REJECTED, note="redo")
    tasks.save_request(resolved)
    assert tasks.get_pending_request("t1") is None
    again = ApprovalRequest("t1", RequestKind.CANCELLATION, "a1", "why")
    tasks.save_request(again)  # a new one may follow a resolved one
    assert tasks.get_pending_request("t1") == again


def test_a_second_pending_request_is_refused_by_the_database(repos: Repos):
    tasks, _ = repos
    tasks.save(make_task(id="t1"))
    tasks.save_request(ApprovalRequest("t1", RequestKind.DELIVERY, "a1", "x"))
    with pytest.raises(IntegrityError, match="UNIQUE"):
        tasks.save_request(ApprovalRequest("t1", RequestKind.CANCELLATION, "a1", "y"))


def test_comments_come_back_in_order(repos: Repos):
    tasks, _ = repos
    tasks.save(make_task(id="t1"))
    first = Comment("t1", "owner", "one", datetime(2026, 11, 26, 10, tzinfo=UTC))
    second = Comment("t1", "a1", "two", datetime(2026, 11, 26, 11, tzinfo=UTC))
    tasks.add_comment(first)
    tasks.add_comment(second)
    assert tasks.comments("t1") == [first, second]
    assert tasks.comments("b1") == []


# --- registry ---------------------------------------------------------------------------------


def test_registry_round_trips_projects_epics_and_agents(repos: Repos):
    _, registry = repos
    assert registry.project_exists("p1") is True
    assert registry.project_exists("e1") is False  # an epic is not a project
    assert registry.project_exists("ghost") is False
    assert registry.get_agent("a1") == PROFILE_A1
    assert registry.get_agent("ghost") is None
    assert registry.list_agents() == [PROFILE_A1, PROFILE_A2]


def test_an_epic_needs_its_project(repos: Repos):
    _, registry = repos
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        registry.save_epic(Epic("e2", "missing", "Epic"))


def test_saving_an_agent_again_updates_it(repos: Repos):
    _, registry = repos
    changed = replace(PROFILE_A1, queue_limit=5, allowed_task_types=frozenset({"chore"}))
    registry.save_agent(changed)
    assert registry.get_agent("a1") == changed
    assert [p.id for p in registry.list_agents()] == ["a1", "a2"]


def test_registry_knows_which_ids_exist_and_which_project_an_epic_belongs_to(repos: Repos):
    _, registry = repos
    assert registry.item_exists("p1") and registry.item_exists("e1") and registry.item_exists("b1")
    assert not registry.item_exists("ghost")
    assert registry.epic_project_id("e1") == "p1"
    assert registry.epic_project_id("p1") is None  # a project is not an epic
    assert registry.epic_project_id("ghost") is None
