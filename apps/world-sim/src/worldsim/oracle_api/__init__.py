"""oracle_api/__init__.py — Oracle API (NEVER routed; evaluation only) (DOC 3 M1 B5).

Endpoints:
  GET /oracle/cashouts?from=<iso>&to=<iso>
  GET /oracle/clusters
  GET /oracle/complaints/{external_ref}/truth

Truth NEVER leaves world-sim except through this API.
This app is never mounted behind Caddy; it only runs on localhost.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException

app = FastAPI(title="NAKABANDI Oracle API (internal only)", version="0")

_store: TruthStore | None = None  # type: ignore[name-defined]  # noqa: F821
_clock: ClockState | None = None  # type: ignore[name-defined]  # noqa: F821

_UTC = UTC


def set_store(store, clock) -> None:  # type: ignore[no-untyped-def]
    """Called once by the CLI before starting uvicorn.

    Takes the live `ClockState` (shared with control_api/runner), not a static run_id string:
    `/control/start` assigns a fresh `clock.run_id` on every start (including after a reset),
    so a run_id captured once at boot would go stale the first time a client actually used the
    control API to reset-then-restart a live session, silently emptying GET /oracle/clusters —
    the hidden-truth source evaluation depends on — for that new run.
    """
    global _store, _clock
    _store = store
    _clock = clock


def _require_store():
    if _store is None:
        raise HTTPException(status_code=503, detail="Oracle not initialised")
    return _store


@app.get("/oracle/cashouts")
def cashouts(from_: str, to: str) -> list[dict]:
    """Return all cash-out truth events in [from_, to] (ISO datetime strings)."""
    store = _require_store()
    try:
        from_dt = datetime.fromisoformat(from_).replace(tzinfo=_UTC)
        to_dt = datetime.fromisoformat(to).replace(tzinfo=_UTC)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return store.get_cashouts_in_range(from_dt, to_dt)


@app.get("/oracle/clusters")
def clusters() -> list[dict]:
    """Return all clusters (including injected) for the current run."""
    store = _require_store()
    run_id = _clock.run_id if _clock is not None else ""
    return store.get_clusters(run_id)


@app.get("/oracle/complaints/{external_ref}/truth")
def complaint_truth(external_ref: str) -> dict:
    """Return the ground-truth for one complaint."""
    store = _require_store()
    result = store.get_complaint_truth(external_ref)
    if result is None:
        raise HTTPException(status_code=404, detail="Truth not found")
    return result
