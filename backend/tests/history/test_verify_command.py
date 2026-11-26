from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from kairos.domain.actor import Actor, ActorKind
from kairos.domain.events import Event, EventType
from kairos.features.history.log import append_events
from kairos.features.history.verify import main

OWNER = Actor(ActorKind.OWNER, "owner")


def _log(engine: Engine, count: int) -> None:
    with engine.begin() as connection:
        events = [Event(EventType.COMMENT_ADDED, "t1", OWNER, {"n": n}) for n in range(count)]
        counter = iter(range(1, 100))
        append_events(
            connection, events, datetime(2026, 11, 26, tzinfo=UTC), lambda: f"e{next(counter)}"
        )


def test_the_command_reports_a_good_log(
    migrated_engine: Engine, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    _log(migrated_engine, 3)
    assert main(["--data-dir", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "OK: 3 events verified"


def test_the_command_accepts_an_empty_log(
    migrated_engine: Engine, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    assert main(["--data-dir", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "OK: 0 events verified"


def test_the_command_reports_the_first_broken_event(
    migrated_engine: Engine, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    _log(migrated_engine, 3)
    with migrated_engine.begin() as connection:
        connection.execute(text("DROP TRIGGER events_no_update"))
        connection.execute(text("UPDATE events SET reason = 'forged' WHERE seq = 2"))
    assert main(["--data-dir", str(tmp_path)]) == 1
    assert capsys.readouterr().out.strip() == "BROKEN at seq 2: hash mismatch"


def test_the_command_does_not_change_the_database(migrated_engine: Engine, tmp_path: Path):
    _log(migrated_engine, 2)
    with migrated_engine.connect() as connection:
        before = connection.execute(text("SELECT count(*), max(hash) FROM events")).one()
    main(["--data-dir", str(tmp_path)])
    with migrated_engine.connect() as connection:
        after = connection.execute(text("SELECT count(*), max(hash) FROM events")).one()
    assert before == after


def test_the_command_says_when_there_is_no_database(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    assert main(["--data-dir", str(tmp_path)]) == 2
    assert "No database" in capsys.readouterr().err
    assert not (tmp_path / "kairos.db").exists()  # looking must not create one
