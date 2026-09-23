"""cli.py — worldsim CLI entry points (DOC 3 M1, B1 scope: `history` only).

Usage:
  worldsim history [--config PATH] [--out PATH] [--seed INT] [--days INT]
  worldsim hash    [--config PATH] [--seed INT] [--days INT]

`history`  generates the full golden stream and writes it as JSONL.
`hash`     generates the stream and prints the sha256 of its content (for CI).

B5 adds: live, sweep-world, ledger, check.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import click

from worldsim.core.clusters import build_clusters
from worldsim.core.config import SimConfig
from worldsim.core.generator import World
from worldsim.core.observe import observe
from worldsim.core.registry import build_registry
from worldsim.core.rng import rng_for
from worldsim.writer.batches import (
    BATCH_MAX,
    _frac_day_to_iso,  # noqa: PLC2701 (internal helper)
    make_idempotency_key,
    to_cashout_batch,
    to_complaint_batch,
    to_hop_batch,
    to_registry,
    to_tick,
)
from worldsim.writer.emitter import JsonlEmitter


def _build_world(cfg: SimConfig) -> World:
    """Construct a seeded World from config."""
    rng = rng_for(cfg.seed, "world")
    registry = build_registry(cfg, rng)
    clusters = build_clusters(cfg, registry, rng)
    return World(cfg=cfg, registry=registry, clusters=clusters)


def _stream_events(world: World, out_emitter: JsonlEmitter, run_id: str) -> str:
    """Generate the full history and emit batches. Returns sha256 of all emitted lines."""
    cfg = world.cfg
    hasher = hashlib.sha256()
    batch_no = 0

    def _emit(batch) -> None:
        nonlocal batch_no
        line = batch.model_dump_json() + "\n"
        out_emitter.emit(batch)
        hasher.update(line.encode())
        batch_no += 1

    # Emit registry first
    _emit(to_registry(world.registry))

    # Step through days
    for day in range(cfg.world.days):
        t0 = float(day)
        t1 = float(day + 1)
        truth_events = world.step(t0, t1)
        step_rng = rng_for(cfg.seed, "observe_step", str(day))
        observed = observe(truth_events, cfg, step_rng)

        from worldsim.core.observe import ObservedCashOut, ObservedComplaint, ObservedHop

        complaints = [e for e in observed if isinstance(e, ObservedComplaint)]
        hops = [e for e in observed if isinstance(e, ObservedHop)]
        cashouts = [e for e in observed if isinstance(e, ObservedCashOut)]
        sim_time_iso = _frac_day_to_iso(t1)

        # Chunk into ≤BATCH_MAX slices (LC-1: maxItems 500)
        for chunk_idx, start in enumerate(range(0, max(len(complaints), 1), BATCH_MAX)):
            chunk = complaints[start : start + BATCH_MAX]
            if not chunk:
                break
            idem = make_idempotency_key(cfg.seed, run_id, batch_no)
            _emit(to_complaint_batch(chunk, sim_time_iso, f"B-{run_id}-C-{day}-{chunk_idx}", idem))

        for chunk_idx, start in enumerate(range(0, max(len(hops), 1), BATCH_MAX)):
            chunk = hops[start : start + BATCH_MAX]
            if not chunk:
                break
            idem = make_idempotency_key(cfg.seed, run_id, batch_no)
            _emit(to_hop_batch(chunk, sim_time_iso, f"B-{run_id}-H-{day}-{chunk_idx}", idem))

        for chunk_idx, start in enumerate(range(0, max(len(cashouts), 1), BATCH_MAX)):
            chunk = cashouts[start : start + BATCH_MAX]
            if not chunk:
                break
            idem = make_idempotency_key(cfg.seed, run_id, batch_no)
            _emit(to_cashout_batch(chunk, sim_time_iso, f"B-{run_id}-CO-{day}-{chunk_idx}", idem))

        _emit(to_tick(sim_time_iso))

    return hasher.hexdigest()


@click.group()
def cli() -> None:
    """NAKABANDI world-sim CLI."""


@cli.command()
@click.option(
    "--config",
    default="config/sim.default.yaml",
    show_default=True,
    help="Path to sim config YAML.",
)
@click.option("--out", default=None, help="Output JSONL file. Defaults to stdout.")
@click.option("--seed", default=None, type=int, help="Override seed in config.")
@click.option("--days", default=None, type=int, help="Override world.days in config.")
def history(config: str, out: str | None, seed: int | None, days: int | None) -> None:
    """Generate the full golden history stream as JSONL."""
    cfg = SimConfig.from_yaml(config)
    if seed is not None:
        cfg = cfg.model_copy(update={"seed": seed})
    if days is not None:
        cfg = cfg.model_copy(update={"world": cfg.world.model_copy(update={"days": days})})

    world = _build_world(cfg)
    run_id = f"golden-{cfg.seed}"
    out_path = Path(out) if out else None

    with JsonlEmitter(out_path) as emitter:
        stream_hash = _stream_events(world, emitter, run_id)

    click.echo(f"stream_hash={stream_hash}", err=True)


@cli.command()
@click.option("--config", default="config/sim.default.yaml", show_default=True)
@click.option("--seed", default=None, type=int)
@click.option("--days", default=None, type=int)
def hash(config: str, seed: int | None, days: int | None) -> None:
    """Print the sha256 of the golden event stream (for CI determinism check)."""
    cfg = SimConfig.from_yaml(config)
    if seed is not None:
        cfg = cfg.model_copy(update={"seed": seed})
    if days is not None:
        cfg = cfg.model_copy(update={"world": cfg.world.model_copy(update={"days": days})})

    world = _build_world(cfg)
    run_id = f"golden-{cfg.seed}"

    # Emit to /dev/null equivalent (count only)
    class _NullEmitter(JsonlEmitter):
        def emit(self, batch):  # type: ignore[override]
            pass

    with _NullEmitter() as emitter:
        stream_hash = _stream_events(world, emitter, run_id)

    click.echo(stream_hash)


if __name__ == "__main__":
    cli()
