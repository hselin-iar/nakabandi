"""npm run evaluate:baselines (ad hoc, DOC 3 Evaluation Harness companion): score hgb against the
three canonical baselines (HotspotBaseline, NearestToVictimBaseline, BankFootprintBaseline) on the
SAME real complaint set scripts/evaluate.py uses, at location/cell/district resolution.

    uv run python scripts/evaluate_baselines.py [--as-of ISO_DATETIME] [--out PATH]

Baselines are built PER COMPLAINT, strictly as-of that complaint's reported_at:
  - HotspotBaseline reads ctx.global_cashout_location_counts (the new as-of global density
    feature, forecast/domain/features.py [NEXT_ACTION]) — not a single global build over the
    whole eval window, which would leak future cash-outs into early complaints' scores.
  - NearestToVictimBaseline scores candidates by haversine distance from the victim's home.
  - BankFootprintBaseline scores candidates in the issuing bank's own network as 1.0.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from nakabandi.evaluation.baselines import (
    BankFootprintBaseline,
    HotspotBaseline,
    NearestToVictimBaseline,
)
from nakabandi.evaluation.metrics import brier_score, hit_rate_at_k, precision_at_k
from nakabandi.forecast import ModelStore
from nakabandi.forecast.domain.scorers import HeuristicScorer, score_candidates
from nakabandi.forecast.domain.timing import MixtureTimingModel
from nakabandi.forecast.domain.types import Candidate, ClusterContext
from nakabandi.forecast.infrastructure.training_data import SqlTrainingDataPort
from nakabandi.geo import GeoService
from nakabandi.graph import ClusterService
from nakabandi.graph.infrastructure.repositories import SqlClusterRepo
from nakabandi.intake import LienContextLookup, latest_ingest_sim_time
from nakabandi.shared import EventBus, Policy, SystemClock, get_settings
from nakabandi.shared.infrastructure.db import create_sqlite_engine, make_session_factory

_KS = (1, 3, 5)
_RESOLUTIONS = ("location", "cell", "district")


def _resolved_id(cand: Candidate, resolution: str) -> str:
    if resolution == "cell":
        return cand.cell_id
    if resolution == "district":
        return cand.district_id
    return cand.location_id


def _ranked_ids(ranked_candidates: list[Candidate], resolution: str) -> list[str]:
    seen: list[str] = []
    for cand in ranked_candidates:
        rid = _resolved_id(cand, resolution)
        if rid not in seen:
            seen.append(rid)
    return seen


def _rank_by_score(candidates: list[Candidate], scores: list[float]) -> list[Candidate]:
    return [c for c, _s in sorted(zip(candidates, scores, strict=True), key=lambda cs: -cs[1])]


def _hgb_scores(
    ctx: ClusterContext, candidates: list[Candidate], scorer, expected_hour: float
) -> list[float]:
    _rows, scores = score_candidates(ctx, candidates, scorer, expected_hour=expected_hour)
    return [float(s) for s in scores]


def _hotspot_scores(ctx: ClusterContext, candidates: list[Candidate]) -> list[float]:
    hotspot = HotspotBaseline(dict(ctx.global_cashout_location_counts))
    return [hotspot.score(c.location_id) for c in candidates]


def _nearest_scores(ctx: ClusterContext, candidates: list[Candidate]) -> list[float]:
    if ctx.layer1_home_lat is None or ctx.layer1_home_lon is None:
        return [0.0 for _ in candidates]
    coords = {c.location_id: (c.lat, c.lon) for c in candidates}
    nearest = NearestToVictimBaseline(coords)
    return [
        nearest.score(c.location_id, ctx.layer1_home_lat, ctx.layer1_home_lon) for c in candidates
    ]


def _bank_footprint_scores(ctx: ClusterContext, candidates: list[Candidate]) -> list[float]:
    bank_locs = {c.location_id for c in candidates if c.bank_id == ctx.layer1_bank_id}
    footprint = BankFootprintBaseline(bank_locs)
    return [footprint.score(c.location_id) for c in candidates]


def _metrics_for(
    records: list[tuple[ClusterContext, list[Candidate], str]],
    score_fn,
) -> dict[str, object]:
    """score_fn(ctx, candidates) -> list[float] raw scores, one per candidate."""
    metrics: dict[str, object] = {}
    for resolution in _RESOLUTIONS:
        preds: list[list[str]] = []
        truth: list[set[str]] = []
        probs: list[float] = []
        outcomes: list[int] = []

        for ctx, candidates, actual_location_id in records:
            scores = score_fn(ctx, candidates)
            ranked_candidates = _rank_by_score(candidates, scores)
            preds.append(_ranked_ids(ranked_candidates, resolution))

            actual_cand = next(c for c in candidates if c.location_id == actual_location_id)
            truth.append({_resolved_id(actual_cand, resolution)})

            if resolution == "location":
                for cand, score in zip(candidates, scores, strict=True):
                    probs.append(float(score))
                    outcomes.append(1 if cand.location_id == actual_location_id else 0)

        res_metrics: dict[str, object] = {"n_complaints": len(records)}
        for k in _KS:
            rate, n = hit_rate_at_k(preds, truth, k)
            res_metrics[f"hit_rate_at_{k}"] = {"value": rate, "n": n}
            prec, n2 = precision_at_k(preds, truth, k)
            res_metrics[f"precision_at_{k}"] = {"value": prec, "n": n2}
        if resolution == "location":
            brier, n_brier = brier_score(probs, outcomes)
            res_metrics["brier_score"] = {"value": brier, "n": n_brier}
        metrics[resolution] = res_metrics
    return metrics


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=str, default=None)
    parser.add_argument("--model-dir", type=str, default="models")
    parser.add_argument("--out", type=str, default="docs/results/baseline_comparison.json")
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
            print("evaluate_baselines: no data ingested yet — nothing to evaluate.")
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
            print("evaluate_baselines: 0 resolved complaints with candidates — nothing to score.")
            return 1

        def hgb_score_fn(ctx: ClusterContext, candidates: list[Candidate]) -> list[float]:
            if timing_model is not None:
                timing = timing_model.horizon_probs(ctx, list(policy.forecast.horizons_min))
                median_min = sum(
                    w * m for w, m in zip(timing.weights, timing.medians_min, strict=False)
                )
                expected_hour = (ctx.reported_at + timedelta(minutes=median_min)).hour
            else:
                expected_hour = 12.0
            return _hgb_scores(ctx, candidates, scorer, expected_hour)

        results: dict[str, dict[str, object]] = {
            scorer_name: _metrics_for(records, hgb_score_fn),
            "hotspot_baseline": _metrics_for(records, _hotspot_scores),
            "nearest_to_victim_baseline": _metrics_for(records, _nearest_scores),
            "bank_footprint_baseline": _metrics_for(records, _bank_footprint_scores),
        }

    report = {
        "generated_at": SystemClock().now().isoformat(),
        "as_of": as_of_end.isoformat(),
        "n_complaints": len(records),
        "results": results,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, default=_json_default))

    print(f"evaluate_baselines: wrote {out_path} ({len(records)} complaints scored)")
    for name, res in results.items():
        loc = res["location"]
        print(
            f"  {name:28s} Hit@1={loc['hit_rate_at_1']['value']:.4f} "
            f"Hit@3={loc['hit_rate_at_3']['value']:.4f} "
            f"Hit@5={loc['hit_rate_at_5']['value']:.4f} "
            f"Prec@5={loc['precision_at_5']['value']:.4f} "
            f"Brier={loc['brier_score']['value']:.4f}"
        )
    return 0


def _json_default(obj: object) -> object:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)  # type: ignore[call-overload]
    return str(obj)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
