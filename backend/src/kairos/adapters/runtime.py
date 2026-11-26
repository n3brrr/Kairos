"""Injected sources of time and identity, so use cases stay deterministic under test."""

from collections.abc import Callable
from datetime import datetime

type Clock = Callable[[], datetime]
"""Returns the current time as a timezone-aware UTC value."""

type NewId = Callable[[], str]
"""Returns a fresh unique identifier."""
