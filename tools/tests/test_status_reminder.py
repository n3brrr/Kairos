from status_reminder import needs_status_update


def test_needs_update_when_code_is_newer_than_status():
    assert needs_status_update(100.0, {"backend/src/kairos/main.py": 200.0})


def test_no_update_needed_when_status_is_newer():
    assert not needs_status_update(300.0, {"backend/src/kairos/main.py": 200.0})


def test_no_update_needed_without_code_changes():
    assert not needs_status_update(100.0, {})
