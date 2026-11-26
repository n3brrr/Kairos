"""Recompute the event chain and report the first event that does not fit.

A hash chain shows that an event was edited, removed from the middle or removed from the front.
It cannot show that the *last* events were cut off (nothing after them points back), and it is
not a security boundary against someone with file access (ADR-0006).
"""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Connection, select

from kairos.adapters.db.engine import make_engine
from kairos.adapters.db.schema import events as events_table
from kairos.config import Settings
from kairos.features.history.hashing import GENESIS_HASH, event_hash


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    checked: int
    broken_at: int | None
    reason: str | None


def verify_chain(conn: Connection) -> VerifyResult:
    """Walk the log from the first event, checking each link and each hash."""
    expected_prev = GENESIS_HASH
    checked = 0
    for row in conn.execute(select(events_table).order_by(events_table.c.seq)).mappings():
        seq = int(row["seq"])
        if row["prev_hash"] != expected_prev:
            reason = "first event does not start the chain" if checked == 0 else "broken link"
            return VerifyResult(False, checked, seq, reason)
        try:
            payload = json.loads(row["payload"])
        except ValueError:
            return VerifyResult(False, checked, seq, "hash mismatch")
        fields = {
            "seq": seq,
            "id": row["id"],
            "at": row["at"],
            "actor_kind": row["actor_kind"],
            "actor_id": row["actor_id"],
            "via": row["via"],
            "entity_id": row["entity_id"],
            "type": row["type"],
            "payload": payload,
            "reason": row["reason"],
        }
        if event_hash(row["prev_hash"], fields) != row["hash"]:
            return VerifyResult(False, checked, seq, "hash mismatch")
        expected_prev = row["hash"]
        checked += 1
    return VerifyResult(True, checked, None, None)


def main(argv: Sequence[str] | None = None) -> int:
    """`python -m kairos.features.history [--data-dir PATH]`: 0 good, 1 broken, 2 no database."""
    parser = argparse.ArgumentParser(
        prog="python -m kairos.features.history", description="Verify the Kairos event chain."
    )
    parser.add_argument("--data-dir", type=Path, default=None, help="folder holding kairos.db")
    data_dir: Path | None = parser.parse_args(argv).data_dir
    settings = Settings(data_dir=data_dir) if data_dir is not None else Settings()
    path = settings.database_path
    if not path.is_file():
        print(f"No database at {path}", file=sys.stderr)
        return 2
    engine = make_engine(path, read_only=True)
    try:
        with engine.connect() as connection:
            result = verify_chain(connection)
    finally:
        engine.dispose()
    if result.ok:
        print(f"OK: {result.checked} events verified")
        return 0
    print(f"BROKEN at seq {result.broken_at}: {result.reason}")
    return 1
