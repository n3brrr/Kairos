"""One transaction over the repositories: it commits when the block ends cleanly."""

from types import TracebackType
from typing import Self

from sqlalchemy import Connection, Engine
from sqlalchemy.engine import RootTransaction

from kairos.features.registry.repository import RegistryRepository
from kairos.features.tasks.repository import TaskRepository


class UnitOfWork:
    """`with UnitOfWork(engine) as uow:` begins a write transaction (`BEGIN IMMEDIATE`).

    It commits at the end of the block, unless `rollback()` was called or the block raised.
    """

    conn: Connection
    tasks: TaskRepository
    registry: RegistryRepository

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._rollback = False
        self._transaction: RootTransaction | None = None

    def __enter__(self) -> Self:
        self.conn = self._engine.connect()
        self._transaction = self.conn.begin()
        self.tasks = TaskRepository(self.conn)
        self.registry = RegistryRepository(self.conn)
        return self

    def rollback(self) -> None:
        """Forget everything written so far; the block still ends normally."""
        self._rollback = True

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        transaction = self._transaction
        try:
            if transaction is not None and transaction.is_active:
                if exc_type is None and not self._rollback:
                    transaction.commit()
                else:
                    transaction.rollback()
        finally:
            self.conn.close()
