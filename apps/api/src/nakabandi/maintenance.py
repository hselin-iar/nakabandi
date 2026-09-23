"""Hosted-demo protections and upkeep (DOC 2 §2.7 "Public exposure", DOC 4 A11): the stream cap,
auto-pause when nobody is watching, and the nightly reset.

Everything here is driven by configuration (env, `shared.Settings`) and does nothing when its
setting is off; nothing product-specific depends on it. Wall-clock throughout: these are
operational concerns, not the simulated timeline."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import structlog
from nakabandi_contracts.ingest import (
    CashOutObservationBatch,
    ComplaintBatch,
    HopBatch,
    RegistryUpdate,
    Tick,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from nakabandi.forecast.infrastructure.repositories import metadata as forecast_metadata
from nakabandi.graph.infrastructure.repositories import metadata as graph_metadata
from nakabandi.intake import IngestService
from nakabandi.interception.infrastructure.repositories import intercept_assessments
from nakabandi.shared import (
    SIM_CLOCK_EPOCH,
    Base,
    Clock,
    SimClock,
    SqlAlchemyUnitOfWork,
    SystemClock,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Stream cap and viewer tracking
# ---------------------------------------------------------------------------


class StreamGate:
    """Counts open SSE streams and enforces the cap (0 = unlimited). Also remembers when a viewer
    was last present, which is what auto-pause reads."""

    def __init__(self, max_streams: int, clock: Clock | None = None) -> None:
        self._max = max_streams
        self._clock = clock or SystemClock()
        self._open = 0
        self._last_viewer_at = self._clock.now()
        self._lock = threading.Lock()

    @property
    def open_streams(self) -> int:
        return self._open

    @property
    def max_streams(self) -> int:
        return self._max

    @property
    def last_viewer_at(self) -> datetime:
        with self._lock:
            return self._clock.now() if self._open else self._last_viewer_at

    def try_open(self) -> bool:
        with self._lock:
            if self._max > 0 and self._open >= self._max:
                return False
            self._open += 1
            return True

    def closed(self) -> None:
        with self._lock:
            self._open = max(0, self._open - 1)
            self._last_viewer_at = self._clock.now()


# ---------------------------------------------------------------------------
# Auto-pause
# ---------------------------------------------------------------------------


def should_pause(
    *, viewers: int, last_viewer_at: datetime, now: datetime, after_min: float
) -> bool:
    """True when nobody is watching and nobody has been for at least `after_min` minutes.
    `after_min <= 0` means the feature is off."""
    if after_min <= 0 or viewers > 0:
        return False
    return now - last_viewer_at >= timedelta(minutes=after_min)


class AutoPause:
    """Pauses the world simulator when nobody has watched for `after_min` minutes (DOC 2 §2.7:
    "world auto-pauses after 15 minutes without a viewer"). It pauses only a RUNNING world, and only
    once per absence: a person who resumes it while nobody is watching is not overruled again until
    a viewer has come and gone."""

    def __init__(
        self,
        gate: StreamGate,
        control_url: str | None,
        after_min: float,
        *,
        clock: Clock | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._gate = gate
        self._url = control_url.rstrip("/") if control_url else None
        self._after_min = after_min
        self._clock = clock or SystemClock()
        self._client = client
        self._paused_this_absence = False

    @property
    def enabled(self) -> bool:
        return self._url is not None and self._after_min > 0

    def tick(self) -> str:
        """One check. Returns what it did: off, watched, waiting, already_handled, not_running,
        paused, or failed."""
        if self._url is None or self._after_min <= 0:
            return "off"
        if self._gate.open_streams > 0:
            self._paused_this_absence = False
            return "watched"
        now = self._clock.now()
        if not should_pause(
            viewers=0,
            last_viewer_at=self._gate.last_viewer_at,
            now=now,
            after_min=self._after_min,
        ):
            return "waiting"
        if self._paused_this_absence:
            return "already_handled"
        try:
            client = self._client or httpx.Client(timeout=5.0)
            try:
                state = client.get(f"{self._url}/status").json().get("state")
                if state != "running":
                    self._paused_this_absence = True  # already paused or stopped: leave it be
                    return "not_running"
                client.post(f"{self._url}/pause").raise_for_status()
            finally:
                if self._client is None:
                    client.close()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("auto_pause.failed", error=str(exc))
            return "failed"
        self._paused_this_absence = True
        logger.info("auto_pause.paused", idle_minutes=self._after_min)
        return "paused"


# ---------------------------------------------------------------------------
# Nightly reset
# ---------------------------------------------------------------------------


def seconds_until(hh_mm: str, now: datetime) -> float:
    """Seconds from `now` to the next occurrence of HH:MM (same tz as `now`); a time that has just
    passed means tomorrow, never zero."""
    hour, minute = (int(part) for part in hh_mm.split(":"))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def create_schema(engine: Engine) -> None:
    """Every table the API needs. forecast, graph and interception keep theirs on MetaData of
    their own (Track B), which Base.create_all does not see; of interception's only
    intercept_assessments is created (its "units" table would clash with geo's)."""
    Base.metadata.create_all(engine)
    forecast_metadata.create_all(engine)
    graph_metadata.create_all(engine)
    intercept_assessments.create(engine, checkfirst=True)


def drop_schema(engine: Engine) -> None:
    intercept_assessments.drop(engine, checkfirst=True)
    graph_metadata.drop_all(engine)
    forecast_metadata.drop_all(engine)
    Base.metadata.drop_all(engine)


_SEED_MODELS = {
    "registry": (RegistryUpdate, "ingest_registry"),
    "complaints": (ComplaintBatch, "ingest_complaints"),
    "hops": (HopBatch, "ingest_hops"),
    "cashout_observations": (CashOutObservationBatch, "ingest_observations"),
    "tick": (Tick, "advance_clock"),
}


@dataclass(frozen=True, slots=True)
class ResetReport:
    seed_lines: int
    accepted: int
    rejected: int


def load_seed_file(
    session_factory: sessionmaker[Session], clock: SimClock, seed_file: Path
) -> ResetReport:
    """Load a JSONL seed (`{"kind", "payload"}` per line) through the SAME intake use cases the
    HTTP routes use (DOC 4 A3: no bypass). Complaints are stored and left for the retry job to
    process, exactly as `npm run seed` does."""
    lines = 0
    accepted = 0
    rejected = 0
    if not seed_file.exists():
        return ResetReport(0, 0, 0)
    for line in seed_file.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        model, method = _SEED_MODELS[record["kind"]]
        with SqlAlchemyUnitOfWork(session_factory) as uow:
            assert uow.session is not None
            response = getattr(IngestService(uow.session, clock), method)(
                model.model_validate(record["payload"])
            )
            uow.commit()
        lines += 1
        accepted += response.accepted
        rejected += len(response.rejected)
    return ResetReport(lines, accepted, rejected)


def reset_database(
    engine: Engine,
    session_factory: sessionmaker[Session],
    clock: SimClock,
    seed_file: Path,
    seed_users: Callable[[Session], None],
) -> ResetReport:
    """Restore the seeded world: drop and recreate every table, put the demo users back, reload
    the seed file, and set the sim clock back to where a fresh process starts. This is what keeps
    the hosted database from growing without bound (DOC 2 §2.7: "database size capped by reset")."""
    drop_schema(engine)
    create_schema(engine)
    clock.reset(SIM_CLOCK_EPOCH)
    with SqlAlchemyUnitOfWork(session_factory) as uow:
        assert uow.session is not None
        seed_users(uow.session)
        uow.commit()
    report = load_seed_file(session_factory, clock, seed_file)
    logger.info(
        "reset.done",
        seed_lines=report.seed_lines,
        accepted=report.accepted,
        rejected=report.rejected,
    )
    return report
