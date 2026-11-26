"""Injected sources of time and identity, so use cases stay deterministic under test."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

type Clock = Callable[[], datetime]
"""Returns the current time as a timezone-aware UTC value."""

type NewId = Callable[[], str]
"""Returns a fresh unique identifier."""


def system_clock() -> datetime:
    """The default `Clock`: the current time in UTC."""
    return datetime.now(UTC)


def uuid_ids() -> str:
    """The default `NewId`: a random UUID as 32 hex characters."""
    return uuid.uuid4().hex
