"""npm run evaluate (DOC 3 Evaluation Harness): score the trained model's candidate rankings
against every resolved complaint in DATABASE_URL and write real metrics for the System
Integrity / Evaluation page to read.

    uv run python scripts/evaluate.py [--as-of ISO_DATETIME] [--out PATH]

Deliberately does NOT use evaluation.run_experiment(): that function's world-generation and
pipeline-injection steps are still stubbed (see evaluation/runner.py's own "STUB NOTE" — B8/B9,
not reached yet). This script instead evaluates the model that's actually running, against
complaints that actually happened, reusing forecast/infrastructure/training_data.py's
already-correct (ctx, candidates, actual_location_id) extraction (the same one scripts/train.py
uses to build training rows) and forecast's own score_candidates() to rank them — the same
ranking GenerateForecast would produce at serving time. No fixture, no invented numbers.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from nakabandi.evaluation.metrics import brier_score, hit_rate_at_k, precision_at_k
from nakabandi.forecast import ModelStore
from nakabandi.forecast.domain.scorers import HeuristicScorer, score_candidates
from nakabandi.forecast.domain.timing import MixtureTimingModel
from nakabandi.forecast.infrastructure.training_data import SqlTrainingDataPort
from nakabandi.geo import GeoService
from nakabandi.graph import ClusterService
from nakabandi.graph.infrastructure.repositories import SqlClusterRepo
from nakabandi.intake import LienContextLookup, latest_ingest_sim_time
from nakabandi.shared import EventBus, Policy, SystemClock, get_settings
from nakabandi.shared.infrastructure.db import create_sqlite_engine, make_session_factory

_KS = (1, 3, 5)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=str, default=None)
    parser.add_argument("--model-dir", type=str, default="models")
    parser.add_argument("--out", type=str, default="apps/web/public/eval-results.json")
    args = parser.parse_args(argv)

    settings = get_settings()
    policy = Policy.load(settings.policy_path)
    engine = create_sqlite_engine(settings.database_url)
    session_factory = make_session_factory(engine)

    with session_factory() as session:
        as_of_end = (
            datetime.fromisoformat(args.as_of).replace(tzinfo=UTC)
            if args.as_of
            else latest_ingest_sim_time(session)
        )
        if as_of_end is None:
            print("evaluate: no data ingested yet — nothing to evaluate.")
            return 1

        data_port = SqlTrainingDataPort(
            cluster_service=ClusterService(SqlClusterRepo(session), EventBus()),
            lien_lookup=LienContextLookup(session),
            geo_service=GeoService(session),
            policy=policy,
        )
        model_store = ModelStore(args.model_dir)
        scorer = model_store.load_scorer() or HeuristicScorer()
        scorer_name = scorer.info().name
        timing_model: MixtureTimingModel | None = model_store.load_timing()

        records = data_port.complaint_records(as_of_end)
        if not records:
            print("evaluate: 0 resolved complaints with candidates — nothing to score.")
            return 1

        preds: list[list[str]] = []
        truth: list[set[str]] = []
        probs: list[float] = []
        outcomes: list[int] = []

        for ctx, candidates, actual_location_id in records:
            # P3: derive expected cash-out hour from the timing model's weighted-median
            # delay so hour_sin/hour_cos carry real information for each complaint.
            # Falls back to noon (12.0) when no timing model has been trained yet.
            if timing_model is not None:
                timing = timing_model.horizon_probs(ctx, list(policy.forecast.horizons_min))
                median_min = sum(
                    w * m for w, m in zip(timing.weights, timing.medians_min, strict=False)
                )
                expected_hour = (ctx.reported_at + timedelta(minutes=median_min)).hour
            else:
                expected_hour = 12.0
            _rows, scores = score_candidates(ctx, candidates, scorer, expected_hour=expected_hour)
            ranked = [
                cand.location_id
                for cand, _score in sorted(
                    zip(candidates, scores, strict=True), key=lambda cs: -cs[1]
                )
            ]
            preds.append(ranked)
            truth.append({actual_location_id})
            for cand, score in zip(candidates, scores, strict=True):
                probs.append(float(score))
                outcomes.append(1 if cand.location_id == actual_location_id else 0)

    metrics: dict[str, object] = {"n_complaints": len(records)}
    for k in _KS:
        rate, n = hit_rate_at_k(preds, truth, k)
        metrics[f"hit_rate_at_{k}"] = {"value": rate, "n": n}
        prec, n2 = precision_at_k(preds, truth, k)
        metrics[f"precision_at_{k}"] = {"value": prec, "n": n2}
    brier, n_brier = brier_score(probs, outcomes)
    metrics["brier_score"] = {"value": brier, "n": n_brier}

    report = {
        "generated_at": SystemClock().now().isoformat(),
        "as_of": as_of_end.isoformat(),
        "scorer": scorer_name,
        "metrics": metrics,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, default=_json_default))

    print(f"evaluate: wrote {out_path} ({len(records)} complaints scored, scorer={scorer_name})")
    print(json.dumps(metrics, indent=2, default=_json_default))
    return 0


def _json_default(obj: object) -> object:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)  # type: ignore[call-overload]
    return str(obj)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
