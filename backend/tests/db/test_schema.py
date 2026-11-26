"""The database refuses what the domain already refuses (defense in depth, ADR-0002)."""

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError

GENESIS = "0" * 64


def _agent(conn: Connection, agent_id: str = "a1") -> None:
    conn.execute(
        text(
            "INSERT INTO agents (id, kind, allowed_task_types, allowed_project_ids, queue_limit)"
            " VALUES (:id, 'agent', '[]', '[]', 3)"
        ),
        {"id": agent_id},
    )


def _project(conn: Connection, project_id: str = "p1") -> None:
    conn.execute(
        text(
            "INSERT INTO items (id, kind, title, status, area)"
            " VALUES (:id, 'project', 'P', 'active', 'Development')"
        ),
        {"id": project_id},
    )


def _task(
    conn: Connection,
    task_id: str,
    status: str = "ready",
    assignee: str | None = None,
    project: str | None = "p1",
) -> None:
    conn.execute(
        text(
            "INSERT INTO items (id, kind, title, status, project_id, type, priority, created_by,"
            " assignee_id) VALUES (:id, 'task', 'T', :status, :project, 'bug', 'P2', 'owner',"
            " :assignee)"
        ),
        {"id": task_id, "status": status, "project": project, "assignee": assignee},
    )


@pytest.fixture
def base(conn: Connection) -> Connection:
    _agent(conn, "a1")
    _agent(conn, "a2")
    _project(conn)
    return conn


def test_two_in_progress_tasks_for_one_agent_are_refused(base: Connection):
    _task(base, "t1", "in_progress", "a1")
    with pytest.raises(IntegrityError, match="UNIQUE"):
        _task(base, "t2", "in_progress", "a1")


def test_a_second_task_may_wait_in_the_queue_or_belong_to_another_agent(base: Connection):
    _task(base, "t1", "in_progress", "a1")
    _task(base, "t2", "ready", "a1")
    _task(base, "t3", "in_progress", "a2")
    _task(base, "t4", "in_review", "a1")


def test_starting_a_second_task_through_an_update_is_refused(base: Connection):
    _task(base, "t1", "in_progress", "a1")
    _task(base, "t2", "ready", "a1")
    with pytest.raises(IntegrityError, match="UNIQUE"):
        base.execute(text("UPDATE items SET status = 'in_progress' WHERE id = 't2'"))


def _request(conn: Connection, task_id: str, state: str, kind: str = "delivery") -> None:
    conn.execute(
        text(
            "INSERT INTO approval_requests (task_id, kind, requested_by, reason, state)"
            " VALUES (:task, :kind, 'a1', 'because', :state)"
        ),
        {"task": task_id, "kind": kind, "state": state},
    )


def test_two_pending_requests_for_one_task_are_refused(base: Connection):
    _task(base, "t1")
    _request(base, "t1", "pending")
    with pytest.raises(IntegrityError, match="UNIQUE"):
        _request(base, "t1", "pending", "cancellation")


def test_resolved_requests_pile_up_next_to_one_pending_request(base: Connection):
    _task(base, "t1")
    _request(base, "t1", "approved")
    _request(base, "t1", "rejected")
    _request(base, "t1", "pending")


def test_an_unknown_task_status_is_refused(base: Connection):
    with pytest.raises(IntegrityError, match="CHECK"):
        _task(base, "t1", "doing")


def test_a_task_needs_a_project(base: Connection):
    with pytest.raises(IntegrityError, match="CHECK"):
        _task(base, "t1", project=None)


def test_a_task_needs_an_existing_project_and_agent(base: Connection):
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        _task(base, "t1", project="missing")
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        _task(base, "t2", assignee="ghost")


def test_a_subtask_status_is_not_a_task_status(base: Connection):
    _task(base, "t1")
    with pytest.raises(IntegrityError, match="CHECK"):
        base.execute(
            text(
                "INSERT INTO items (id, kind, title, status, parent_id)"
                " VALUES ('s1', 'subtask', 'S', 'ready', 't1')"
            )
        )
    base.execute(
        text(
            "INSERT INTO items (id, kind, title, status, parent_id)"
            " VALUES ('s2', 'subtask', 'S', 'in_review', 't1')"
        )
    )


def test_an_epic_has_no_stored_status_and_no_task_fields(base: Connection):
    with pytest.raises(IntegrityError, match="CHECK"):
        base.execute(
            text(
                "INSERT INTO items (id, kind, title, status, parent_id)"
                " VALUES ('e1', 'epic', 'E', 'active', 'p1')"
            )
        )
    with pytest.raises(IntegrityError, match="CHECK"):
        base.execute(
            text(
                "INSERT INTO items (id, kind, title, parent_id, type)"
                " VALUES ('e2', 'epic', 'E', 'p1', 'bug')"
            )
        )
    base.execute(
        text("INSERT INTO items (id, kind, title, parent_id) VALUES ('e3', 'epic', 'E', 'p1')")
    )


def test_a_project_needs_an_area(base: Connection):
    with pytest.raises(IntegrityError, match="CHECK"):
        base.execute(
            text(
                "INSERT INTO items (id, kind, title, status)"
                " VALUES ('p2', 'project', 'P', 'active')"
            )
        )


def test_a_task_cannot_block_itself(base: Connection):
    _task(base, "t1")
    with pytest.raises(IntegrityError, match="CHECK"):
        base.execute(text("INSERT INTO dependencies (task_id, blocker_id) VALUES ('t1', 't1')"))


def _event(conn: Connection, event_id: str, prev_hash: str, hash_: str) -> None:
    conn.execute(
        text(
            "INSERT INTO events (id, at, actor_kind, actor_id, via, entity_id, type, payload,"
            " reason, prev_hash, hash) VALUES (:id, '2026-11-26T10:00:00+00:00', 'owner', 'owner',"
            " NULL, 't1', 'item_created', '{}', NULL, :prev, :hash)"
        ),
        {"id": event_id, "prev": prev_hash, "hash": hash_},
    )


def test_events_form_a_chain_and_refuse_an_update_or_a_delete(conn: Connection):
    _event(conn, "e1", GENESIS, "1" * 64)
    _event(conn, "e2", "1" * 64, "2" * 64)
    with pytest.raises(IntegrityError, match="events is append-only"):
        conn.execute(text("UPDATE events SET reason = 'x' WHERE id = 'e1'"))
    with pytest.raises(IntegrityError, match="events is append-only"):
        conn.execute(text("DELETE FROM events WHERE id = 'e1'"))


def test_an_event_that_does_not_continue_the_chain_is_refused(conn: Connection):
    with pytest.raises(IntegrityError, match="chain"):
        _event(conn, "e1", "f" * 64, "1" * 64)  # the first event must start from the genesis
    _event(conn, "e1", GENESIS, "1" * 64)
    with pytest.raises(IntegrityError, match="chain"):
        _event(conn, "e2", GENESIS, "2" * 64)  # must continue from the last hash
