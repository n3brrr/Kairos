"""The tables, as SQLAlchemy Core metadata: the one description of the schema.

The migration in `migrations/versions/` is written out by hand (so a later change here cannot
rewrite history); `tests/db/test_migrations.py` checks that both agree. Triggers live only in the
migration: they are not part of the metadata.
"""

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    text,
)

metadata = MetaData()

task_types = Table(
    "task_types",
    metadata,
    Column("name", Text, primary_key=True),
    Column("required_fields", JSON, nullable=False),
    Column("criteria_template", JSON, nullable=False),
)

agents = Table(
    "agents",
    metadata,
    Column("id", Text, primary_key=True),
    Column("kind", Text, nullable=False),
    Column("allowed_task_types", JSON, nullable=False),
    Column("allowed_project_ids", JSON, nullable=False),
    Column("queue_limit", Integer, nullable=False),
    CheckConstraint("kind IN ('agent', 'orchestrator')", name="ck_agents_kind"),
    CheckConstraint("queue_limit >= 1", name="ck_agents_queue_limit"),
)

# One table for projects, epics, tasks and subtasks (design §6.1). Task-only columns are NULL
# for the other kinds; the CHECKs below tie each column to its kind.
items = Table(
    "items",
    metadata,
    Column("id", Text, primary_key=True),
    Column("kind", Text, nullable=False),
    Column("parent_id", Text, ForeignKey("items.id")),
    Column("title", Text, nullable=False),
    Column("status", Text),
    Column("position", Integer, nullable=False, server_default="0"),
    Column("area", Text),
    Column("project_id", Text, ForeignKey("items.id")),
    Column("type", Text, ForeignKey("task_types.name")),
    Column("priority", Text),
    Column("description", Text, nullable=False, server_default=""),
    Column("labels", JSON, nullable=False, server_default="[]"),
    Column("start_date", Date),
    Column("due_date", Date),
    Column("recurrence", Text),
    Column("created_by", Text),
    Column("assignee_id", Text, ForeignKey("agents.id")),
    Column("delivery_summary", Text, nullable=False, server_default=""),
    Column("working_notes", Text, nullable=False, server_default=""),
    CheckConstraint("kind IN ('project', 'epic', 'task', 'subtask')", name="ck_items_kind"),
    CheckConstraint(
        "(kind = 'project' AND status IN ('active', 'queued', 'paused', 'archived'))"
        " OR (kind = 'epic' AND status IS NULL)"
        " OR (kind = 'task' AND status IN ('proposed', 'backlog', 'ready', 'in_progress',"
        " 'in_review', 'done', 'cancelled'))"
        " OR (kind = 'subtask' AND status IN ('todo', 'in_progress', 'in_review', 'done',"
        " 'cancelled'))",
        name="ck_items_status",
    ),
    CheckConstraint(
        "(kind = 'project' AND parent_id IS NULL)"
        " OR (kind IN ('epic', 'subtask') AND parent_id IS NOT NULL)"
        " OR kind = 'task'",
        name="ck_items_parent",
    ),
    CheckConstraint("(kind = 'project') = (area IS NOT NULL)", name="ck_items_area"),
    CheckConstraint(
        "(kind = 'task' AND project_id IS NOT NULL AND type IS NOT NULL"
        " AND priority IS NOT NULL AND created_by IS NOT NULL)"
        " OR (kind <> 'task' AND project_id IS NULL AND type IS NULL AND priority IS NULL"
        " AND created_by IS NULL AND assignee_id IS NULL)",
        name="ck_items_task_fields",
    ),
    CheckConstraint(
        "priority IS NULL OR priority IN ('P0', 'P1', 'P2', 'P3')", name="ck_items_priority"
    ),
)
Index("ix_items_parent", items.c.parent_id)
# Defense in depth for design §6.8: one `in_progress` task per agent, whatever the code does.
Index(
    "one_in_progress_per_agent",
    items.c.assignee_id,
    unique=True,
    sqlite_where=text("kind = 'task' AND status = 'in_progress'"),
)

criteria = Table(
    "criteria",
    metadata,
    Column("task_id", Text, ForeignKey("items.id"), primary_key=True),
    Column("id", Text, primary_key=True),
    Column("position", Integer, nullable=False),
    Column("text", Text, nullable=False),
)

evidence = Table(
    "evidence",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("task_id", Text, nullable=False),
    Column("criterion_id", Text, nullable=False),
    Column("position", Integer, nullable=False),
    Column("kind", Text, nullable=False),
    Column("content", Text, nullable=False),
    Column("added_by", Text, nullable=False),
    ForeignKeyConstraint(["task_id", "criterion_id"], ["criteria.task_id", "criteria.id"]),
    CheckConstraint("kind IN ('text', 'link', 'command_output')", name="ck_evidence_kind"),
)

dependencies = Table(
    "dependencies",
    metadata,
    Column("task_id", Text, ForeignKey("items.id"), primary_key=True),
    Column("blocker_id", Text, ForeignKey("items.id"), primary_key=True),
    CheckConstraint("task_id <> blocker_id", name="ck_dependencies_not_self"),
)

comments = Table(
    "comments",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("task_id", Text, ForeignKey("items.id"), nullable=False),
    Column("author", Text, nullable=False),
    Column("text", Text, nullable=False),
    Column("at", Text, nullable=False),
)

approval_requests = Table(
    "approval_requests",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("task_id", Text, ForeignKey("items.id"), nullable=False),
    Column("kind", Text, nullable=False),
    Column("requested_by", Text, nullable=False),
    Column("reason", Text, nullable=False),
    Column("state", Text, nullable=False),
    Column("note", Text),
    CheckConstraint("kind IN ('delivery', 'cancellation')", name="ck_requests_kind"),
    CheckConstraint("state IN ('pending', 'approved', 'rejected')", name="ck_requests_state"),
)
Index(
    "one_pending_request_per_task",
    approval_requests.c.task_id,
    unique=True,
    sqlite_where=text("state = 'pending'"),
)

# The append-only, hash-chained history (ADR-0006). Triggers forbid UPDATE and DELETE and check
# the chain on insert; they are created by the migration.
events = Table(
    "events",
    metadata,
    Column("seq", Integer, primary_key=True, autoincrement=True),
    Column("id", Text, nullable=False, unique=True),
    Column("at", Text, nullable=False),
    Column("actor_kind", Text, nullable=False),
    Column("actor_id", Text, nullable=False),
    Column("via", Text),
    Column("entity_id", Text, nullable=False),
    Column("type", Text, nullable=False),
    Column("payload", Text, nullable=False),
    Column("reason", Text),
    Column("prev_hash", Text, nullable=False),
    Column("hash", Text, nullable=False, unique=True),
    sqlite_autoincrement=True,
)
Index("ix_events_entity", events.c.entity_id, events.c.seq)
