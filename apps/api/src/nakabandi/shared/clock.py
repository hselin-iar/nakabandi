"""Clock protocol; SystemClock; SimClock (DOC 3 Shared Kernel, LC-9).

This is the ONLY file allowed to read the wall clock (`datetime.now`); every other file reads
time through an injected Clock (AP-10 / ruff TID251, per-file-ignored here in pyproject.toml).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

import structlog

from nakabandi.shared.types import SimTime

logger = structlog.get_logger(__name__)


class Clock(Protocol):
    def now(self) -> SimTime: ...


class SystemClock:
    """Wall time in UTC. The only place `datetime.now` may appear (LC-9)."""

    def now(self) -> SimTime:
        return datetime.now(UTC)


class SimClock:
    """Simulated time, owned and advanced explicitly. Monotonic: advancing to an earlier or
    equal time is ignored and logged once per occurrence, never raised (edge case in the
    Shared Kernel spec)."""

    def __init__(self, start: SimTime) -> None:
        self._current = start

    def now(self) -> SimTime:
        return self._current

    def advance_to(self, t: SimTime) -> None:
        if t <= self._current:
            logger.warning(
                "sim_clock.advance_to.ignored_non_monotonic",
                requested=t.isoformat(),
                current=self._current.isoformat(),
            )
            return
        self._current = t
