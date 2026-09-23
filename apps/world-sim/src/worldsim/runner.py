"""runner.py — LiveRunner (speed loop) (DOC 3 M1 B5).

LiveRunner.run(world, emitter, speed_getter, clock_state):
  Loop every TICK_REAL_S real seconds:
    - advance sim time by speed × elapsed_real
    - call World.step(t0, t1)
    - observe the events
    - push due observed events (priority queue keyed by observed_at) in batches
    - emit Tick(now_sim)

Invariants (DOC 3 M1):
  - Speed changes never duplicate or skip simulated time.
  - Pause/resume: the loop suspends at the end of the current tick; resumes cleanly.
  - Injected cluster while paused: cluster is added to world.clusters; takes effect on resume.
  - Reset: caller stops the runner; runner does not manage DB directly.

SRP: runner never generates world content; core/generator.py does that.
"""

from __future__ import annotations

import heapq
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from threading import Event, Lock

from worldsim.core.generator import (
    CashOutTruth,
    ComplaintTruth,
    TruthEvent,
    World,
)
from worldsim.core.observe import ObservedCashOut, ObservedComplaint, ObservedHop, observe
from worldsim.core.rng import rng_for
from worldsim.truth_store import TruthStore
from worldsim.writer.batches import (
    BATCH_MAX,
    _frac_day_to_iso,  # noqa: PLC2701
    make_idempotency_key,
    to_cashout_batch,
    to_complaint_batch,
    to_hop_batch,
    to_tick,
)
from worldsim.writer.emitter import ApiEmitter

logger = logging.getLogger(__name__)

TICK_REAL_S: float = 0.5  # real-time seconds per sim loop iteration
_UTC = UTC


class RunnerState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STALLED = "stalled"  # emitter stalled; sim is paused until flush
    STOPPED = "stopped"


@dataclass
class ClockState:
    """Mutable sim-clock state shared between runner and control API."""

    now_sim: float = 0.0  # fractional sim days elapsed since run start
    speed: float = 1.0  # sim seconds per real second (1–60)
    run_id: str = ""
    seed: int = 42
    scenario: str = "free"

    # Counts for the status endpoint
    complaints_total: int = 0
    cashouts_total: int = 0
    ticks_total: int = 0
    last_error: str | None = None


@dataclass
class _QueuedEvent:
    """Observed event held in the priority queue until its observed_at is due."""

    observed_at: float  # fractional sim days
    kind: str  # "complaint" | "hop" | "cashout"
    payload: ObservedComplaint | ObservedHop | ObservedCashOut

    def __lt__(self, other: _QueuedEvent) -> bool:
        return self.observed_at < other.observed_at


class LiveRunner:
    """Real-time simulation loop.

    Thread-safety: `pause`, `resume`, `set_speed`, `inject_cluster`, and `stop` may
    be called from the FastAPI control-API thread. All state mutations are protected
    by `_lock`.
    """

    def __init__(
        self,
        world: World,
        emitter: ApiEmitter,
        truth_store: TruthStore,
        clock_state: ClockState,
    ) -> None:
        self._world = world
        self._emitter = emitter
        self._store = truth_store
        self._clock = clock_state
        self._lock = Lock()
        self._pause_event = Event()
        self._pause_event.set()  # starts unpaused
        self._stop_event = Event()
        self._state = RunnerState.IDLE
        self._pending: list[_QueuedEvent] = []  # min-heap by observed_at

    # ------------------------------------------------------------------
    # Control methods (called from the API thread)
    # ------------------------------------------------------------------

    @property
    def state(self) -> RunnerState:
        return self._state

    def pause(self) -> None:
        with self._lock:
            if self._state == RunnerState.RUNNING:
                self._pause_event.clear()
                self._state = RunnerState.PAUSED

    def resume(self) -> None:
        with self._lock:
            if self._state in (RunnerState.PAUSED, RunnerState.STALLED):
                self._state = RunnerState.RUNNING
                self._pause_event.set()

    def set_speed(self, factor: float) -> None:
        """Change speed (1–60). Never duplicates or skips sim time: speed only affects
        how much sim time advances per real tick going forward."""
        factor = max(1.0, min(60.0, factor))
        with self._lock:
            self._clock.speed = factor

    def stop(self) -> None:
        self._stop_event.set()
        self._pause_event.set()  # unblock if paused

    def inject_cluster(
        self,
        district_id: str,
        size: int,
        fast_weight: float,
        locality: str,
    ) -> str:
        """Add a never-seen cluster. If paused, takes effect on resume (DOC 3 M1)."""
        cluster_id = f"INJ-{uuid.uuid4().hex[:8].upper()}"
        # Build a minimal cluster and append to world
        # (full build_clusters logic not needed for injection)
        with self._lock:
            # Persist to truth store so oracle API can see it
            self._store.save_cluster(
                run_id=self._clock.run_id,
                cluster_id=cluster_id,
                district_id=district_id,
                size=size,
                fast_weight=fast_weight,
                locality=locality,
            )
            # Add to world so future steps can route complaints to it
            from worldsim.core.scenarios import inject_cluster as _inject

            _inject(
                self._world,
                district_id=district_id,
                size=size,
                fast_weight=fast_weight,
                locality=locality,
                sim_now=self._clock.now_sim,
            )
        logger.info(
            "runner.inject_cluster cluster_id=%s district_id=%s",
            cluster_id,
            district_id,
        )
        return cluster_id

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Block the calling thread running the simulation until stop() is called."""
        self._state = RunnerState.RUNNING
        clock = self._clock

        self._store.begin_run(clock.run_id, clock.seed, clock.scenario)

        last_real = time.monotonic()
        sim_now = clock.now_sim  # local copy to avoid lock contention in tight loop

        try:
            while not self._stop_event.is_set():
                # --- Wait if paused ---
                self._pause_event.wait()
                if self._stop_event.is_set():
                    break

                real_now = time.monotonic()
                elapsed_real = real_now - last_real
                last_real = real_now

                with self._lock:
                    speed = clock.speed

                # Advance sim time (fractional days = elapsed_real × speed / 86400)
                sim_elapsed = elapsed_real * speed / 86_400.0
                sim_t0 = sim_now
                sim_t1 = sim_now + sim_elapsed
                sim_now = sim_t1

                with self._lock:
                    clock.now_sim = sim_now

                # --- Generate truth events ---
                truth_events: list[TruthEvent] = self._world.step(sim_t0, sim_t1)

                if truth_events:
                    event_dt = datetime.now(_UTC)  # noqa: TID251 — runner infra, no injected Clock
                    complaints = [e for e in truth_events if isinstance(e, ComplaintTruth)]
                    cashouts = [e for e in truth_events if isinstance(e, CashOutTruth)]
                    self._store.save_complaints(clock.run_id, complaints, event_dt)
                    self._store.save_cashouts(clock.run_id, cashouts, event_dt)

                # --- Observe ---
                step_rng = rng_for(clock.seed, "live_observe", str(clock.ticks_total))
                observed = observe(truth_events, self._world.cfg, step_rng)

                sim_time_dt: datetime = _frac_day_to_iso(sim_t1)  # returns datetime
                batch_no_base = clock.ticks_total * 10  # rough unique batch counter

                # Enqueue observed events into priority queue
                for ev in observed:
                    if isinstance(ev, ObservedComplaint):
                        heapq.heappush(
                            self._pending,
                            _QueuedEvent(ev.observed_at, "complaint", ev),
                        )
                    elif isinstance(ev, ObservedHop):
                        heapq.heappush(self._pending, _QueuedEvent(ev.observed_at, "hop", ev))
                    elif isinstance(ev, ObservedCashOut):
                        heapq.heappush(self._pending, _QueuedEvent(ev.observed_at, "cashout", ev))

                # Drain events that are due (observed_at <= sim_now)
                due_complaints: list[ObservedComplaint] = []
                due_hops: list[ObservedHop] = []
                due_cashouts: list[ObservedCashOut] = []

                while self._pending and self._pending[0].observed_at <= sim_now:
                    qe = heapq.heappop(self._pending)
                    if qe.kind == "complaint":
                        due_complaints.append(qe.payload)  # type: ignore[arg-type]
                    elif qe.kind == "hop":
                        due_hops.append(qe.payload)  # type: ignore[arg-type]
                    elif qe.kind == "cashout":
                        due_cashouts.append(qe.payload)  # type: ignore[arg-type]

                # Emit due batches
                run_id = clock.run_id
                bn = batch_no_base
                if not self._emit_batches(
                    due_complaints, due_hops, due_cashouts, sim_time_dt, run_id, bn
                ):
                    # Emitter stalled
                    with self._lock:
                        self._state = RunnerState.STALLED
                        self._pause_event.clear()
                        clock.last_error = self._emitter.last_error
                    continue

                # Emit Tick
                tick = to_tick(_frac_day_to_iso(sim_t1))
                self._emitter.emit("/ingest/tick", tick)

                with self._lock:
                    clock.ticks_total += 1
                    clock.complaints_total += len(due_complaints)
                    clock.cashouts_total += len(due_cashouts)
                    if self._state == RunnerState.RUNNING:
                        clock.last_error = None

                time.sleep(TICK_REAL_S)

        except Exception as exc:
            logger.exception("runner.loop.fatal: %s", str(exc))
            with self._lock:
                clock.last_error = str(exc)
        finally:
            self._state = RunnerState.STOPPED
            self._store.end_run(clock.run_id)

    def _emit_batches(
        self,
        complaints: list[ObservedComplaint],
        hops: list[ObservedHop],
        cashouts: list[ObservedCashOut],
        sim_time: datetime,
        run_id: str,
        batch_no_base: int,
    ) -> bool:
        """Emit all due batches. Returns False if the emitter enters STALLED state."""
        cfg = self._world.cfg
        bn = batch_no_base

        for chunk_start in range(0, max(len(complaints), 1), BATCH_MAX):
            chunk = complaints[chunk_start : chunk_start + BATCH_MAX]
            if not chunk:
                break
            idem = make_idempotency_key(cfg.seed, run_id, bn)
            batch = to_complaint_batch(chunk, sim_time, f"L-{run_id}-C-{bn}", idem)
            self._emitter.emit("/ingest/complaints", batch)
            bn += 1
            if self._emitter.state.value == "stalled":
                return False

        for chunk_start in range(0, max(len(hops), 1), BATCH_MAX):
            chunk = hops[chunk_start : chunk_start + BATCH_MAX]
            if not chunk:
                break
            idem = make_idempotency_key(cfg.seed, run_id, bn)
            batch = to_hop_batch(chunk, sim_time, f"L-{run_id}-H-{bn}", idem)
            self._emitter.emit("/ingest/hops", batch)
            bn += 1
            if self._emitter.state.value == "stalled":
                return False

        for chunk_start in range(0, max(len(cashouts), 1), BATCH_MAX):
            chunk = cashouts[chunk_start : chunk_start + BATCH_MAX]
            if not chunk:
                break
            idem = make_idempotency_key(cfg.seed, run_id, bn)
            batch = to_cashout_batch(chunk, sim_time, f"L-{run_id}-CO-{bn}", idem)
            self._emitter.emit("/ingest/cashouts", batch)
            bn += 1
            if self._emitter.state.value == "stalled":
                return False

        return True
