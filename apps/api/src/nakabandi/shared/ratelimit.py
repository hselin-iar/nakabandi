"""SlidingWindowLimiter: the one rate limiter (DOC 2 §2.7: login and control endpoints).

Wall-clock, never the SimClock: like LC-6's webhook timestamp window this is a transport-level
abuse control, not a simulated-time domain event (DOC 2 §2.4). State is in memory and per
instance, so a fresh `create_app()` (every test makes its own) starts with clean counters."""

from __future__ import annotations

import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta

from nakabandi.shared.clock import Clock, SystemClock


class SlidingWindowLimiter:
    """At most `max_events` per `window` per key. `allow(key)` records the event and returns
    True, or returns False (recording nothing) when the key is over its limit. `max_events <= 0`
    means unlimited, so a limit can be switched off by configuration."""

    def __init__(self, max_events: int, window: timedelta, clock: Clock | None = None) -> None:
        self._max = max_events
        self._window = window
        self._clock = clock or SystemClock()
        self._events: dict[str, deque[datetime]] = defaultdict(deque)
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._max > 0

    def allow(self, key: str) -> bool:
        if not self.enabled:
            return True
        now = self._clock.now()
        with self._lock:
            events = self._events[key]
            while events and now - events[0] > self._window:
                events.popleft()
            if len(events) >= self._max:
                return False
            events.append(now)
            if len(self._events) > 10_000:  # a scan would otherwise grow the table without bound
                self._prune(now)
            return True

    def _prune(self, now: datetime) -> None:
        for key in [k for k, ev in self._events.items() if not ev or now - ev[-1] > self._window]:
            del self._events[key]
