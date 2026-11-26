import json

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Connection, Engine, inspect, text

from kairos.adapters.db.migrate import downgrade, upgrade
from kairos.adapters.db.schema import metadata

EXPECTED_TABLES = {
    "agents",
    "approval_requests",
    "comments",
    "criteria",
    "dependencies",
    "events",
    "evidence",
    "items",
    "task_types",
}


def _tables(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def test_upgrade_creates_every_table(migrated_engine: Engine):
    assert _tables(migrated_engine) == EXPECTED_TABLES


def test_upgrade_is_idempotent(migrated_engine: Engine):
    upgrade(migrated_engine)
    assert _tables(migrated_engine) == EXPECTED_TABLES


def test_downgrade_to_base_removes_everything_and_upgrade_restores_it(migrated_engine: Engine):
    downgrade(migrated_engine, "base")
    assert _tables(migrated_engine) == set()
    with migrated_engine.connect() as connection:
        triggers = connection.execute(text("SELECT name FROM sqlite_master WHERE type = 'trigger'"))
        assert triggers.all() == []
    upgrade(migrated_engine)
    assert _tables(migrated_engine) == EXPECTED_TABLES


def test_the_migrated_database_matches_the_table_definitions(conn: Connection):
    context = MigrationContext.configure(conn, opts={"compare_type": True})
    assert compare_metadata(context, metadata) == []


def test_the_five_task_types_are_seeded(conn: Connection):
    rows = conn.execute(text("SELECT name, required_fields FROM task_types ORDER BY name")).all()
    assert [name for name, _ in rows] == ["bug", "chore", "feature", "personal", "research"]
    required = {name: set(json.loads(fields)) for name, fields in rows}
    assert required["bug"] == {"description"}
    assert required["feature"] == {"description", "priority"}
    assert required["chore"] == set()


def test_the_defense_triggers_and_indexes_exist(conn: Connection):
    def names(kind: str) -> set[str]:
        rows = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type = :kind"), {"kind": kind}
        )
        return {row[0] for row in rows}

    assert {"events_no_update", "events_no_delete", "events_chain_check"} <= names("trigger")
    assert {"one_in_progress_per_agent", "one_pending_request_per_task"} <= names("index")
