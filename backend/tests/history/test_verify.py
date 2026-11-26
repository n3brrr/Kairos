from datetime import UTC, datetime
from itertools import count

import pytest
from sqlalchemy import Connection, text

from kairos.domain.actor import Actor, ActorKind
from kairos.domain.events import Event, EventType
from kairos.features.history.log import append_events
from kairos.features.history.verify import VerifyResult, verify_chain

OWNER = Actor(ActorKind.OWNER, "owner")
AT = datetime(2026, 11, 26, 10, 0, tzinfo=UTC)


def _five(conn: Connection) -> None:
    ids = count(1)
    events = [
        Event(EventType.COMMENT_ADDED, "t1", OWNER, {"text": f"note {n}"}) for n in range(1, 6)
    ]
    append_events(conn, events, AT, lambda: f"ev{next(ids)}")


def _allow_tampering(conn: Connection) -> None:
    """Drop the guards, as someone with file access could: the chain must still show it."""
    for trigger in ("events_no_update", "events_no_delete"):
        conn.execute(text(f"DROP TRIGGER {trigger}"))


def test_an_empty_log_verifies(conn: Connection):
    assert verify_chain(conn) == VerifyResult(ok=True, checked=0, broken_at=None, reason=None)


def test_an_untouched_log_verifies(conn: Connection):
    _five(conn)
    assert verify_chain(conn) == VerifyResult(ok=True, checked=5, broken_at=None, reason=None)


def test_editing_a_payload_is_found_at_that_event(conn: Connection):
    _five(conn)
    _allow_tampering(conn)
    conn.execute(text("""UPDATE events SET payload = '{"text":"forged"}' WHERE seq = 3"""))
    result = verify_chain(conn)
    assert (result.ok, result.broken_at, result.reason) == (False, 3, "hash mismatch")


def test_deleting_a_middle_event_breaks_the_link_after_it(conn: Connection):
    _five(conn)
    _allow_tampering(conn)
    conn.execute(text("DELETE FROM events WHERE seq = 3"))
    result = verify_chain(conn)
    assert (result.ok, result.broken_at, result.reason) == (False, 4, "broken link")


def test_swapping_two_payloads_is_found_at_the_first_of_them(conn: Connection):
    _five(conn)
    _allow_tampering(conn)
    conn.execute(text("""UPDATE events SET payload = '{"text":"note 3"}' WHERE seq = 2"""))
    conn.execute(text("""UPDATE events SET payload = '{"text":"note 2"}' WHERE seq = 3"""))
    result = verify_chain(conn)
    assert (result.ok, result.broken_at, result.reason) == (False, 2, "hash mismatch")


def test_deleting_the_first_event_means_the_chain_has_no_start(conn: Connection):
    _five(conn)
    _allow_tampering(conn)
    conn.execute(text("DELETE FROM events WHERE seq = 1"))
    result = verify_chain(conn)
    expected = (False, 2, "first event does not start the chain")
    assert (result.ok, result.broken_at, result.reason) == expected


@pytest.mark.parametrize("column", ["reason", "actor_id", "via", "at", "type", "entity_id"])
def test_editing_any_hashed_column_is_found(conn: Connection, column: str):
    _five(conn)
    _allow_tampering(conn)
    conn.execute(text(f"UPDATE events SET {column} = 'changed' WHERE seq = 4"))
    result = verify_chain(conn)
    assert result.ok is False
    assert result.broken_at == 4
