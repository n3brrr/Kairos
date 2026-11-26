"""Run the Alembic migrations against an engine, without an `alembic.ini`."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

_SCRIPTS = Path(__file__).parent / "migrations"


def _config(engine: Engine) -> Config:
    config = Config()
    config.set_main_option("script_location", str(_SCRIPTS))
    config.attributes["engine"] = engine
    return config


def upgrade(engine: Engine, revision: str = "head") -> None:
    command.upgrade(_config(engine), revision)


def downgrade(engine: Engine, revision: str) -> None:
    command.downgrade(_config(engine), revision)
