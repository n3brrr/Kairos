from kairos.features.history.hashing import GENESIS_HASH, canonical_json, event_hash

RECORD = {
    "seq": 1,
    "id": "e1",
    "at": "2026-11-26T10:00:00+00:00",
    "actor_kind": "owner",
    "actor_id": "owner",
    "via": None,
    "entity_id": "t1",
    "type": "item_created",
    "payload": {"b": 1, "a": "é"},
    "reason": None,
}


def test_genesis_is_sixty_four_zeros():
    assert GENESIS_HASH == "0" * 64


def test_canonical_json_ignores_key_order_and_keeps_unicode():
    assert canonical_json({"b": 1, "a": "é"}) == '{"a":"é","b":1}'
    assert canonical_json({"a": "é", "b": 1}) == canonical_json({"b": 1, "a": "é"})


def test_canonical_json_orders_nested_keys_and_has_no_spaces():
    assert canonical_json({"z": {"y": [1, 2], "x": None}}) == '{"z":{"x":null,"y":[1,2]}}'


def test_the_hash_format_is_pinned():
    # Computed once, outside the implementation, with hashlib over
    # GENESIS + canonical JSON. If this changes, every stored chain breaks.
    expected = "a21b88d33800fa1d2e6b6e68cccd288bc887adced6a42a26d53c4471c6ad32e3"
    assert event_hash(GENESIS_HASH, RECORD) == expected


def test_the_previous_hash_and_every_field_change_the_hash():
    base = event_hash(GENESIS_HASH, RECORD)
    assert event_hash("1" * 64, RECORD) != base
    for field, other in (("seq", 2), ("reason", "why"), ("payload", {"a": "é"}), ("via", "sub")):
        assert event_hash(GENESIS_HASH, {**RECORD, field: other}) != base, field
