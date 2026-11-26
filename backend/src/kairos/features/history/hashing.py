"""How an event's hash is made. Pure and standard-library only (ADR-0006).

`hash = sha256(prev_hash + canonical_json(record))` in hex, where the record holds the event's
`seq`, `id`, `at`, actor, `via`, entity, type, payload and reason. Canonical JSON sorts keys,
has no spaces and keeps unicode as it is, so the same record always gives the same text.
"""

import hashlib
import json
from collections.abc import Mapping

GENESIS_HASH = "0" * 64


def canonical_json(value: Mapping[str, object]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def event_hash(prev_hash: str, record: Mapping[str, object]) -> str:
    return hashlib.sha256((prev_hash + canonical_json(record)).encode("utf-8")).hexdigest()
