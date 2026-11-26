"""Appending to and reading the event log. Writing joins the caller's transaction."""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import Connection, RowMapping, insert, select

from kairos.adapters.db.schema import events as events_table
from kairos.adapters.runtime import NewId
from kairos.domain.actor import ActorKind
from kairos.domain.events import Event, EventType
from kairos.features.history.hashing import GENESIS_HASH, canonical_json, event_hash


@dataclass(frozen=True)
class EventRecord:
    """One stored event, with the link and the hash that chain it to the one before."""

    seq: int
    id: str
    at: datetime
    actor_kind: ActorKind
    actor_id: str
    via: str | None
    entity_id: str
    type: EventType
    payload: Mapping[str, object]
    reason: str | None
    prev_hash: str
    hash: str

    def hash_fields(self) -> dict[str, object]:
        """The record that gets hashed: everything except the two hashes themselves."""
        return {
            "seq": self.seq,
            "id": self.id,
            "at": self.at.isoformat(),
            "actor_kind": self.actor_kind.value,
            "actor_id": self.actor_id,
            "via": self.via,
            "entity_id": self.entity_id,
            "type": self.type.value,
            "payload": self.payload,
            "reason": self.reason,
        }


def append_events(
    conn: Connection, events: Sequence[Event], at: datetime, new_id: NewId
) -> list[EventRecord]:
    """Chain `events` after the last stored one. Never commits: the caller's transaction owns it."""
    if at.tzinfo is None:
        raise ValueError("The event timestamp needs a timezone.")
    if not events:
        return []
    last = conn.execute(
        select(events_table.c.seq, events_table.c.hash).order_by(events_table.c.seq.desc()).limit(1)
    ).first()
    seq, prev_hash = (last.seq, last.hash) if last is not None else (0, GENESIS_HASH)
    stamp = at.astimezone(UTC)
    records: list[EventRecord] = []
    for event in events:
        seq += 1
        payload = cast(Mapping[str, object], json.loads(canonical_json(event.payload)))
        record = EventRecord(
            seq=seq,
            id=new_id(),
            at=stamp,
            actor_kind=event.actor.kind,
            actor_id=event.actor.id,
            via=event.actor.via,
            entity_id=event.entity_id,
            type=event.type,
            payload=payload,
            reason=event.reason,
            prev_hash=prev_hash,
            hash="",
        )
        digest = event_hash(prev_hash, record.hash_fields())
        record = replace(record, hash=digest)
        conn.execute(
            insert(events_table).values(
                seq=record.seq,
                id=record.id,
                at=record.at.isoformat(),
                actor_kind=record.actor_kind.value,
                actor_id=record.actor_id,
                via=record.via,
                entity_id=record.entity_id,
                type=record.type.value,
                payload=canonical_json(record.payload),
                reason=record.reason,
                prev_hash=record.prev_hash,
                hash=record.hash,
            )
        )
        records.append(record)
        prev_hash = digest
    return records


def list_events(
    conn: Connection, *, entity_id: str | None = None, after_seq: int = 0, limit: int = 100
) -> list[EventRecord]:
    """Events in `seq` order, after `after_seq`, optionally for one entity."""
    query = select(events_table).where(events_table.c.seq > after_seq)
    if entity_id is not None:
        query = query.where(events_table.c.entity_id == entity_id)
    rows = conn.execute(query.order_by(events_table.c.seq).limit(limit))
    return [row_to_record(row) for row in rows.mappings()]


def row_to_record(row: RowMapping) -> EventRecord:
    return EventRecord(
        seq=cast(int, row["seq"]),
        id=cast(str, row["id"]),
        at=datetime.fromisoformat(cast(str, row["at"])),
        actor_kind=ActorKind(cast(str, row["actor_kind"])),
        actor_id=cast(str, row["actor_id"]),
        via=cast("str | None", row["via"]),
        entity_id=cast(str, row["entity_id"]),
        type=EventType(cast(str, row["type"])),
        payload=cast(Mapping[str, object], json.loads(cast(str, row["payload"]))),
        reason=cast("str | None", row["reason"]),
        prev_hash=cast(str, row["prev_hash"]),
        hash=cast(str, row["hash"]),
    )
