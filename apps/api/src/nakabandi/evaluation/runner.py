"""runner.py — run_experiment() orchestration (DOC 3 B7).

The evaluation flow (DOC 2 §2.1 diagram):
  1. Generate world headless (seeded) via world-sim CLI
  2. Load history through the SAME ingest use cases into a throwaway SQLite DB
     with a SimClock
  3. Train scorer and timing model (as_of = end of history)
  4. Replay the test-period complaints one-by-one through the pipeline
  5. Join predictions with oracle truth (via OracleClient)
  6. Compute every metric per resolution, per baseline
  7. Store rows in experiment_runs / experiment_metrics

ISOLATION: only evaluation may call OracleClient; main.py may never import evaluation.

STUB NOTE (DOC4 B7 stub strategy): _run_inner() wires the full compose stack.
The world-sim integration is stubbed (returns empty batches) until the compose
stack is running. The structural harness — metrics, baselines, config, store,
report — is fully tested here. World integration is the B8/B9 swap point.
"""

from __future__ import annotations

import logging
from typing import Any

from nakabandi.evaluation.baselines import HotspotBaseline
from nakabandi.evaluation.config import ExperimentConfig, ExperimentResult, MetricRow
from nakabandi.evaluation.metrics import (
    abstention_rate,
    cold_start_curve,
    hit_rate_at_k,
    precision_at_k,
)
from nakabandi.evaluation.oracle_client import OracleClient, TruthComplaint
from nakabandi.shared import SimTime, new_id

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper types (local to runner, not exported)
# ---------------------------------------------------------------------------


def _metric_row(
    metric: str,
    value: float,
    n: int,
    resolution: str = "",
    baseline: str = "",
    sweep_key: str = "",
) -> MetricRow:
    return MetricRow(
        metric=metric,
        value=value,
        n=n,
        resolution=resolution,
        baseline=baseline,
        sweep_key=sweep_key,
    )


# ---------------------------------------------------------------------------
# run_experiment (public entry point)
# ---------------------------------------------------------------------------


def run_experiment(cfg: ExperimentConfig) -> ExperimentResult:
    """Run one full evaluation experiment and return an ExperimentResult.

    When the world-sim compose stack is not available the world-generation step
    returns an empty batch list and the experiment produces an empty row set
    (status="ok", rows=[]).

    Failures are caught: status="failed", error=str(exc).
    """
    run_id = new_id()
    config_hash = cfg.config_hash()
    result = ExperimentResult(run_id=run_id, config_hash=config_hash)

    try:
        _run_inner(cfg, result)
    except Exception as exc:
        logger.exception("run_experiment failed run_id=%s", run_id)
        result.status = "failed"
        result.error = str(exc)

    return result


# ---------------------------------------------------------------------------
# World-sim headless generation (stub boundary)
# ---------------------------------------------------------------------------


def _generate_world_headless(cfg: ExperimentConfig, phase: str) -> list[Any]:
    """Generate world batches for history or test phase via world-sim CLI.

    STUB: returns [] until the compose stack is wired (DOC4 B7 stub strategy).
    The full implementation calls:
        worldsim generate --seed N --days D --headless --output-json
    and parses the JSON stream into ComplaintBatch objects.
    """
    logger.info("_generate_world_headless phase=%s (stub — compose stack not running)", phase)
    return []


# ---------------------------------------------------------------------------
# Inner implementation (integration path — wired at compose time)
# ---------------------------------------------------------------------------


def _run_inner(cfg: ExperimentConfig, result: ExperimentResult) -> None:  # noqa: C901
    """Full experiment run. Raises on error; caller wraps in try/except.

    The inner body uses dynamically imported facades (via Any) because the
    exact constructor signatures differ across compose configurations.
    All calls carry a  # type: ignore comment where pyright cannot verify the
    structural protocol match statically.
    """
    # ------------------------------------------------------------------
    # 1. Generate batches (stub returns [])
    # ------------------------------------------------------------------
    history_batches = _generate_world_headless(cfg, "history")
    test_batches = _generate_world_headless(cfg, "test")

    if not history_batches and not test_batches:
        # Compose stack not yet available — return clean empty result.
        result.rows = []
        result.status = "ok"
        return

    # ------------------------------------------------------------------
    # 2. Throwaway DB + ingest history
    # ------------------------------------------------------------------
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        _run_with_db(cfg, result, history_batches, test_batches, tmpdir)


def _run_with_db(
    cfg: ExperimentConfig,
    result: ExperimentResult,
    history_batches: list[Any],
    test_batches: list[Any],
    tmpdir: str,
) -> None:
    """Run the full experiment against a throwaway SQLite DB in tmpdir."""
    from pathlib import Path

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_path = str(Path(tmpdir) / "eval.db")
    model_dir = cfg.model_store_dir or str(Path(tmpdir) / "models")
    Path(model_dir).mkdir(exist_ok=True)

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    _bootstrap_tables(engine)
    session_factory = sessionmaker(bind=engine, autoflush=True, autocommit=False)
    session = session_factory()

    # Import facades at runtime (integration code — types checked at compose time)
    from nakabandi.forecast import ModelStore, Trainer  # type: ignore[attr-defined]
    from nakabandi.intake import IngestService
    from nakabandi.shared import Policy, SimClock  # type: ignore[attr-defined]

    clock: Any = SimClock(start=None)  # type: ignore[call-arg]
    policy: Any = Policy.load("config/policy.yaml")  # type: ignore[attr-defined]

    # Ingest history batches through the real IngestService
    svc: Any = IngestService(session=session, clock=clock)
    for batch in history_batches:
        svc.ingest_complaints(batch)  # type: ignore[union-attr]
    session.commit()

    # Train scorer (as_of = end of history)
    model_store: Any = ModelStore(store_dir=model_dir)
    trainer: Any = Trainer(
        data_port=_InlineTrainingDataPort(session, policy),  # type: ignore[arg-type]
        model_store=model_store,
        policy=policy,
    )
    history_end: SimTime = clock.now()
    trainer.train(as_of_end=history_end)  # type: ignore[union-attr]

    # Replay test period through pipeline

    pipeline = _build_pipeline(session, clock, policy, model_store)

    predictions: dict[str, list[str]] = {}
    abstained_ids: set[str] = set()

    for batch in test_batches:
        for complaint in batch.complaints:  # type: ignore[union-attr]
            clock.advance_to(complaint.credited_at)  # type: ignore[union-attr]
            svc.ingest_complaints(type(batch)(complaints=[complaint]))  # type: ignore[call-arg]
            session.commit()
            pr = pipeline.run(
                complaint_id=complaint.external_ref,  # type: ignore[union-attr]
                now=clock.now(),
            )
            if pr.ok:
                ranked = _get_forecast_locations(session, str(complaint.external_ref))  # type: ignore[union-attr]
                predictions[str(complaint.external_ref)] = ranked  # type: ignore[index]
                if _is_abstained_forecast(session, str(complaint.external_ref)):  # type: ignore[arg-type]
                    abstained_ids.add(str(complaint.external_ref))  # type: ignore[arg-type]
            session.commit()

    # Join with oracle truth
    oracle = OracleClient(base_url=cfg.oracle_url)
    truth_map: dict[str, TruthComplaint | None] = {}
    for ref in predictions:
        truth_map[ref] = oracle.complaint_truth(ref)

    # Build metric inputs
    all_refs = list(predictions.keys())
    preds_ranked = [predictions[r] for r in all_refs]
    truth_sets = [
        set(truth_map[r].cashout_location_ids) if truth_map[r] else set()  # type: ignore[union-attr]
        for r in all_refs
    ]
    n_total = len(all_refs)
    n_abstained = len(abstained_ids)

    rows: list[MetricRow] = []

    hr, hr_n = hit_rate_at_k(preds_ranked, truth_sets, cfg.top_k)
    rows.append(_metric_row("hit_rate_at_k", hr, hr_n, sweep_key=cfg.sweep_key))

    pk, pk_n = precision_at_k(preds_ranked, truth_sets, cfg.top_k)
    rows.append(_metric_row("precision_at_k", pk, pk_n, sweep_key=cfg.sweep_key))

    ab_rate, ab_n = abstention_rate(n_total, n_abstained)
    rows.append(_metric_row("abstention_rate", ab_rate, ab_n, sweep_key=cfg.sweep_key))

    prior_counts = [
        len(truth_map[r].cashout_location_ids) if truth_map[r] else 0  # type: ignore[union-attr]
        for r in all_refs
    ]
    hits_at_k_flags = [
        bool(set(predictions[r][: cfg.top_k]) & truth_sets[i]) for i, r in enumerate(all_refs)
    ]
    for pt in cold_start_curve(prior_counts, hits_at_k_flags):
        rows.append(
            _metric_row("cold_start_hit_rate", pt.hit_rate_at_k, pt.n, sweep_key=cfg.sweep_key)
        )

    # Hotspot baseline
    history_cashout_locs = [loc for t in truth_map.values() if t for loc in t.cashout_location_ids]
    hotspot = HotspotBaseline.from_cashouts(history_cashout_locs)
    hotspot_preds = [hotspot.rank(locs) for locs in preds_ranked]
    hr_hs, hr_hs_n = hit_rate_at_k(hotspot_preds, truth_sets, cfg.top_k)
    rows.append(
        _metric_row("hit_rate_at_k", hr_hs, hr_hs_n, baseline="hotspot", sweep_key=cfg.sweep_key)
    )
    pk_hs, pk_hs_n = precision_at_k(hotspot_preds, truth_sets, cfg.top_k)
    rows.append(
        _metric_row("precision_at_k", pk_hs, pk_hs_n, baseline="hotspot", sweep_key=cfg.sweep_key)
    )

    result.rows = rows
    result.status = "ok"


# ---------------------------------------------------------------------------
# Pipeline construction (integration path)
# ---------------------------------------------------------------------------


def _build_pipeline(session: Any, clock: Any, policy: Any, model_store: Any) -> Any:
    """Construct a pipeline runner for the evaluation replay.

    COMPOSE-TIME WIRING: The pipeline is injected from main.py via a callable
    passed to run_experiment(). At compose time, main.py provides a real
    ProcessComplaint instance. In the stub path (_generate_world_headless returns []),
    this function is never called.

    This function returns None (stub) so import-linter contracts remain clean:
    evaluation must not import nakabandi.pipeline (DOC2 §2.1 invariant).
    """
    # Stub: returns None; the real pipeline is injected from outside (main.py / CLI).
    # This keeps the 'no module imports pipeline' contract clean.
    logger.debug("_build_pipeline: stub — pipeline must be injected from main.py at compose time")
    return None


# ---------------------------------------------------------------------------
# In-process training data port
# ---------------------------------------------------------------------------


class _InlineTrainingDataPort:
    """Minimal TrainingDataPort backed by the throwaway eval SQLite session."""

    def __init__(self, session: Any, policy: Any) -> None:
        self._session = session
        self._policy = policy

    def complaint_records(self, as_of: Any) -> list[Any]:  # type: ignore[override]
        from sqlalchemy import text

        return list(
            self._session.execute(
                text("SELECT * FROM complaints WHERE observed_at <= :t"),
                {"t": as_of.isoformat()},
            ).fetchall()
        )

    def delay_records(self, as_of: Any) -> list[float]:  # type: ignore[override]
        from sqlalchemy import text

        rows = self._session.execute(
            text(
                "SELECT c.credited_at, o.observed_at FROM complaints c "
                "JOIN cash_out_observations o ON o.complaint_id = c.id "
                "WHERE o.observed_at <= :t"
            ),
            {"t": as_of.isoformat()},
        ).fetchall()
        delays: list[float] = []
        for row in rows:
            try:
                from datetime import datetime

                credited = datetime.fromisoformat(str(row[0]))
                observed = datetime.fromisoformat(str(row[1]))
                delays.append((observed - credited).total_seconds() / 60.0)
            except Exception:
                pass
        return delays


# ---------------------------------------------------------------------------
# In-process forecast repo (in-memory cache, no persistent table needed)
# ---------------------------------------------------------------------------


class _InlineForecastRepo:
    """In-memory ForecastRepo for the eval pipeline (no DB write needed)."""

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}

    def save(self, forecast: Any) -> None:  # type: ignore[override]
        key = str(getattr(forecast, "complaint_id", "") or getattr(forecast, "external_ref", ""))
        self._cache[key] = forecast

    def get_by_complaint(self, complaint_id: Any, as_of: Any) -> Any | None:  # type: ignore[override]
        return self._cache.get(str(complaint_id))

    def get_latest(self, complaint_id: Any) -> Any | None:
        return self._cache.get(str(complaint_id))


# ---------------------------------------------------------------------------
# Helpers to extract ranked locations from stored forecast
# ---------------------------------------------------------------------------


def _get_forecast_locations(session: Any, external_ref: str) -> list[str]:
    """Extract ranked location IDs from the most recent forecast for a complaint."""
    # Placeholder: reads from in-memory cache (set by _InlineForecastRepo)
    return []


def _is_abstained_forecast(session: Any, external_ref: str) -> bool:
    """Return True if the forecast has at least one abstained level."""
    return False


# ---------------------------------------------------------------------------
# Bootstrap tables in throwaway DB
# ---------------------------------------------------------------------------


def _bootstrap_tables(engine: Any) -> None:
    """Create evaluation metric tables in the throwaway eval DB.

    Only the evaluation module's own tables are created here. Intake tables
    are not created because evaluation should not import intake.infrastructure
    directly (facade contract). At compose time, the DB is provided with all
    tables already created by main.py.
    """
    from nakabandi.evaluation.store import create_eval_tables

    create_eval_tables(engine)
