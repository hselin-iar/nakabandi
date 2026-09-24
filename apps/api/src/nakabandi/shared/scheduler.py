"""Scheduler: in-memory timers driven by a Clock (DOC 3 Shared Kernel).

Timers live in memory only; owners (alerting) rebuild theirs from database rows at boot
(RebuildTimers, M4) rather than relying on this surviving a restart.
"""

from __future__ import annotations

import heapq
import itertools
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

import structlog

from nakabandi.shared.types import SimTime

logger = structlog.get_logger(__name__)


@dataclass(order=True)
class _Entry:
    at: SimTime
    seq: int
    key: str = field(compare=False)
    fn: Callable[[], None] = field(compare=False)
    cancelled: bool = field(default=False, compare=False)


class Scheduler:
    """A heap keyed by time, plus a dict for O(1) cancel/replace by key."""

    def __init__(self) -> None:
        self._heap: list[_Entry] = []
        self._by_key: dict[str, _Entry] = {}
        self._seq = itertools.count()
        # Request threads schedule timers while the timer worker fires them, so every touch of
        # the heap is under this lock. Callbacks run OUTSIDE it: a callback may schedule again.
        self._lock = threading.RLock()

    def call_at(self, key: str, at: SimTime, fn: Callable[[], None]) -> None:
        """Schedule `fn` at `at`. Replaces any existing timer with the same key: the old entry
        is marked cancelled (lazily dropped from the heap) and the new one wins."""
        with self._lock:
            if key in self._by_key:
                self._by_key[key].cancelled = True
            entry = _Entry(at=at, seq=next(self._seq), key=key, fn=fn)
            self._by_key[key] = entry
            heapq.heappush(self._heap, entry)

    def cancel(self, key: str) -> None:
        with self._lock:
            entry = self._by_key.pop(key, None)
            if entry is not None:
                entry.cancelled = True

    def has_due(self, now: SimTime) -> bool:
        """Is any live timer due at `now`? Cheap: a driver can skip a tick with nothing to do."""
        with self._lock:
            while self._heap and self._heap[0].cancelled:
                heapq.heappop(self._heap)
            return bool(self._heap) and self._heap[0].at <= now

    def run_due(self, now: SimTime) -> int:
        """Fire every timer with `at <= now`, in time order. A callback exception is logged and
        does not stop the remaining due timers. Returns the count fired."""
        fired = 0
        while True:
            with self._lock:
                if not self._heap or self._heap[0].at > now:
                    break
                entry = heapq.heappop(self._heap)
                if entry.cancelled:
                    continue
                if self._by_key.get(entry.key) is entry:
                    del self._by_key[entry.key]
            try:
                entry.fn()
            except Exception:
                logger.exception("scheduler.timer.failed", key=entry.key, at=entry.at.isoformat())
            fired += 1
        return fired
