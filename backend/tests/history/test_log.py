from datetime import UTC, datetime
from itertools import count

import pytest
from sqlalchemy import Connection

from kairos.domain.actor import Actor, ActorKind
from kairos.domain.events import Event, EventType
from kairos.features.history.hashing import GENESIS_HASH, event_hash
from kairos.features.history.log import EventRecord, append_events, list_events

OWNER = Actor(ActorKind.OWNER, "owner")
AGENT = Actor(ActorKind.AGENT, "a1", via="helper")
AT = datetime(2026, 11, 26, 10, 0, tzinfo=UTC)


def _ids():
    counter = count(1)
    return lambda: f"ev{next(counter)}"


def _event(entity: str = "t1", actor: Actor = OWNER, reason: str | None = None) -> Event:
    return Event(EventType.COMMENT_ADDED, entity, actor, {"text": "hi", "tags": ("a", "b")}, reason)


def _hash_again(record: EventRecord) -> str:
    return event_hash(
        record.prev_hash,
        {
            "seq": record.seq,
            "id": record.id,
            "at": record.at.isoformat(),
            "actor_kind": record.actor_kind.value,
            "actor_id": record.actor_id,
            "via": record.via,
            "entity_id": record.entity_id,
            "type": record.type.value,
            "payload": record.payload,
            "reason": record.reason,
        },
    )


def test_appended_events_are_numbered_and_chained(conn: Connection):
    records = append_events(conn, [_event(), _event(), _event()], AT, _ids())
    assert [r.seq for r in records] == [1, 2, 3]
    assert records[0].prev_hash == GENESIS_HASH
    assert records[1].prev_hash == records[0].hash
    assert records[2].prev_hash == records[1].hash
    assert all(r.hash == _hash_again(r) for r in records)
    assert len({r.id for r in records}) == 3


def test_a_later_call_continues_the_chain(conn: Connection):
    (first,) = append_events(conn, [_event()], AT, _ids())
    (second,) = append_events(conn, [_event()], AT, lambda: "other")
    assert second.seq == 2
    assert second.prev_hash == first.hash


def test_who_why_and_via_round_trip(conn: Connection):
    append_events(conn, [_event(actor=AGENT, reason="because")], AT, _ids())
    (stored,) = list_events(conn)
    assert stored.actor_kind is ActorKind.AGENT
    assert stored.actor_id == "a1"
    assert stored.via == "helper"
    assert stored.reason == "because"
    assert stored.type is EventType.COMMENT_ADDED
    assert stored.payload == {"text": "hi", "tags": ["a", "b"]}  # tuples come back as lists
    assert stored.at == AT


def test_appending_nothing_writes_nothing(conn: Connection):
    assert append_events(conn, [], AT, _ids()) == []
    assert list_events(conn) == []


def test_a_naive_timestamp_is_refused(conn: Connection):
    with pytest.raises(ValueError, match="timezone"):
        append_events(conn, [_event()], datetime(2026, 11, 26, 10, 0), _ids())
    assert list_events(conn) == []


def test_list_events_filters_by_entity_and_pages_by_seq(conn: Connection):
    append_events(conn, [_event("t1"), _event("t2"), _event("t1"), _event("t2")], AT, _ids())
    assert [r.seq for r in list_events(conn, entity_id="t1")] == [1, 3]
    assert [r.seq for r in list_events(conn, after_seq=2)] == [3, 4]
    assert [r.seq for r in list_events(conn, limit=2)] == [1, 2]
    assert [r.seq for r in list_events(conn, entity_id="t2", after_seq=2, limit=1)] == [4]


def test_a_rolled_back_transaction_leaves_the_log_empty(conn: Connection):
    append_events(conn, [_event(), _event()], AT, _ids())
    conn.rollback()
    assert list_events(conn) == []
    (record,) = append_events(conn, [_event()], AT, _ids())
    assert record.seq == 1
    assert record.prev_hash == GENESIS_HASH
