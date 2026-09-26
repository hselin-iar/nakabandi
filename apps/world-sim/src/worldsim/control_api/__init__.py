"""control_api/__init__.py — FastAPI app for the simulator control API (DOC 3 M1 LC-8 B5).

Endpoints (LC-8):
  POST /control/start           { scenario, speed? }
  POST /control/pause
  POST /control/resume
  POST /control/speed           { factor: 1..60 }
  POST /control/reset           { seed? }  — admin only, gated at the proxy
  POST /control/inject-cluster  { district_id, size, fast_weight, locality }
  GET  /control/status          -> { state, sim_time, speed, seed, counts, scenario, last_error }

The control API mutates the runner via thread-safe methods on LiveRunner.
Error responses follow the standard JSON envelope: { "error": "..." }.
"""

from __future__ import annotations

import threading
import uuid
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="NAKABANDI World-Sim Control API", version="0")

# ---------------------------------------------------------------------------
# Shared runner state (set by the CLI `live` command before starting uvicorn)
# ---------------------------------------------------------------------------
# These are intentionally module-level so that the FastAPI app and the CLI's
# background thread share the same objects without dependency injection.

_runner: LiveRunner | None = None  # type: ignore[name-defined]  # noqa: F821
_world: World | None = None  # type: ignore[name-defined]  # noqa: F821
_clock: ClockState | None = None  # type: ignore[name-defined]  # noqa: F821
_runner_thread: threading.Thread | None = None


def set_runner(runner, world, clock) -> None:  # type: ignore[no-untyped-def]
    """Called once by the CLI before starting uvicorn."""
    global _runner, _world, _clock
    _runner = runner
    _world = world
    _clock = clock


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class StartRequest(BaseModel):
    scenario: Literal["free", "guided_demo"] = "free"
    speed: float = Field(default=1.0, ge=1.0, le=60.0)


class SpeedRequest(BaseModel):
    factor: float = Field(ge=1.0, le=60.0)


class ResetRequest(BaseModel):
    seed: int | None = None


class InjectClusterRequest(BaseModel):
    district_id: str
    size: int = Field(ge=1, le=500)
    fast_weight: float = Field(ge=0.0, le=1.0)
    locality: Literal["district", "multi_district", "state", "multi_state"] = "district"


class StatusResponse(BaseModel):
    state: str
    sim_time: float
    speed: float
    seed: int
    scenario: str
    counts: dict[str, int]
    last_error: str | None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


def _require_runner():
    if _runner is None or _clock is None:
        raise HTTPException(status_code=503, detail="Runner not initialised")
    return _runner, _clock


@app.post("/control/start")
def start(req: StartRequest) -> dict:
    runner, clock = _require_runner()
    from worldsim.runner import RunnerState

    if runner.state not in (RunnerState.IDLE, RunnerState.STOPPED):
        raise HTTPException(status_code=409, detail=f"Runner already {runner.state}")

    clock.scenario = req.scenario
    clock.speed = req.speed
    clock.run_id = f"run-{uuid.uuid4().hex[:12]}"

    global _runner_thread
    _runner_thread = threading.Thread(target=runner.run, daemon=True)
    _runner_thread.start()
    return {"status": "started", "run_id": clock.run_id}


@app.post("/control/pause")
def pause() -> dict:
    runner, _ = _require_runner()
    runner.pause()
    return {"status": "paused"}


@app.post("/control/resume")
def resume() -> dict:
    runner, _ = _require_runner()
    runner.resume()
    return {"status": "resumed"}


@app.post("/control/speed")
def speed(req: SpeedRequest) -> dict:
    runner, clock = _require_runner()
    runner.set_speed(req.factor)
    return {"status": "ok", "speed": clock.speed}


@app.post("/control/reset")
def reset(req: ResetRequest) -> dict:
    """Admin only; gated at the Caddy proxy with forward_auth."""
    global _world
    runner, clock = _require_runner()
    runner.stop()
    if _runner_thread and _runner_thread.is_alive():
        _runner_thread.join(timeout=5.0)

    # Re-seed if requested — and actually rebuild the world's registry/clusters on the new
    # seed, not just the reported clock.seed: World.step() draws from the World's own frozen
    # cfg.seed, set once at CLI startup, so generation used to silently keep running on the
    # OLD seed forever after a "reset". Rebuilding also clears any clusters injected before
    # the reset (world.clusters starts fresh), matching DOC3's reset edge-case table
    # ("restores seeded state... wipes world.db").
    if req.seed is not None:
        clock.seed = req.seed
        from worldsim.cli import _build_world  # local import: cli owns world construction

        new_cfg = runner._world.cfg.model_copy(update={"seed": req.seed})
        new_world = _build_world(new_cfg)
        runner._world = new_world
        _world = new_world

    # Reset counts
    clock.now_sim = 0.0
    clock.complaints_total = 0
    clock.cashouts_total = 0
    clock.ticks_total = 0
    clock.last_error = None
    clock.run_id = ""

    # Wipe truth store
    if hasattr(runner, "_store"):
        runner._store.reset()

    return {"status": "reset", "seed": clock.seed}


@app.post("/control/inject-cluster")
def inject_cluster(req: InjectClusterRequest) -> dict:
    runner, clock = _require_runner()
    from worldsim.runner import RunnerState

    if runner.state not in (RunnerState.RUNNING, RunnerState.PAUSED):
        raise HTTPException(status_code=409, detail="Runner must be running or paused to inject")
    cluster_id = runner.inject_cluster(
        district_id=req.district_id,
        size=req.size,
        fast_weight=req.fast_weight,
        locality=req.locality,
    )
    return {"status": "injected", "cluster_id": cluster_id}


@app.get("/control/status")
def status() -> StatusResponse:
    runner, clock = _require_runner()
    return StatusResponse(
        state=runner.state.value,
        sim_time=clock.now_sim,
        speed=clock.speed,
        seed=clock.seed,
        scenario=clock.scenario,
        counts={
            "complaints": clock.complaints_total,
            "cashouts": clock.cashouts_total,
            "ticks": clock.ticks_total,
        },
        last_error=clock.last_error,
    )
