"""Metrics: in-process counters and latency samples behind GET /system/metrics (DOC 2 §2.7: "events
per second, stage latencies p50 and p95, outbox depth, delivery failures").

Everything here is WALL-clock and process-local: it measures how the API is running, not the
simulated world. Numbers are a sliding window over recent samples, so an idle process reads zero
rather than a stale average."""

from __future__ import annotations

import math
import threading
import time
from collections import defaultdict, deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta

from nakabandi.shared.clock import Clock, SystemClock
from nakabandi.shared.events import DomainEvent, EventBus


@dataclass(frozen=True, slots=True)
class LatencySummary:
    count: int
    p50_ms: float
    p95_ms: float
    max_ms: float


def percentile(sorted_values: list[float], p: float) -> float:
    """Nearest-rank percentile of an ascending list (p in 0..1); 0.0 for an empty list."""
    if not sorted_values:
        return 0.0
    rank = max(1, math.ceil(p * len(sorted_values)))
    return sorted_values[rank - 1]


class Metrics:
    def __init__(
        self,
        *,
        clock: Clock | None = None,
        rate_window: timedelta = timedelta(seconds=60),
        max_samples: int = 2048,
    ) -> None:
        self._clock = clock or SystemClock()
        self._rate_window = rate_window
        self._counts: dict[str, deque[tuple[datetime, int]]] = defaultdict(deque)
        self._totals: dict[str, int] = defaultdict(int)
        self._samples: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=max_samples))
        self._lock = threading.Lock()

    def incr(self, name: str, n: int = 1) -> None:
        if n <= 0:
            return
        now = self._clock.now()
        with self._lock:
            self._totals[name] += n
            q = self._counts[name]
            q.append((now, n))
            self._trim(q, now)

    def observe(self, name: str, seconds: float) -> None:
        with self._lock:
            self._samples[name].append(seconds)

    @contextmanager
    def timer(self, name: str) -> Iterator[None]:
        """Time a block (a monotonic duration, not a wall time) and record it under `name`, even
        if the block raises."""
        start = time.perf_counter()
        try:
            yield
        finally:
            self.observe(name, time.perf_counter() - start)

    def total(self, name: str) -> int:
        with self._lock:
            return self._totals[name]

    def rate(self, name: str) -> float:
        """Events per second over the sliding window. The window is the elapsed time since the
        first event still inside it (at most `rate_window`), so a burst that just began is not
        divided by a minute it has not lived yet."""
        now = self._clock.now()
        with self._lock:
            q = self._counts[name]
            self._trim(q, now)
            if not q:
                return 0.0
            span = max((now - q[0][0]).total_seconds(), 1.0)
            return sum(n for _, n in q) / min(span, self._rate_window.total_seconds())

    def latency(self, name: str) -> LatencySummary:
        with self._lock:
            values = sorted(self._samples[name])
        return LatencySummary(
            count=len(values),
            p50_ms=percentile(values, 0.50) * 1000,
            p95_ms=percentile(values, 0.95) * 1000,
            max_ms=(values[-1] * 1000) if values else 0.0,
        )

    def latency_names(self) -> list[str]:
        with self._lock:
            return sorted(n for n, s in self._samples.items() if s)

    def _trim(self, q: deque[tuple[datetime, int]], now: datetime) -> None:
        while q and now - q[0][0] > self._rate_window:
            q.popleft()


class MeteredEventBus(EventBus):
    """An EventBus that counts what it publishes (the "events per second" number)."""

    def __init__(self, metrics: Metrics) -> None:
        super().__init__()
        self._metrics = metrics

    def publish(self, event: DomainEvent) -> None:
        self._metrics.incr("events")
        super().publish(event)
