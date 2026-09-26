"""npm run train (DOC 3 M2 B6): fit the v1 forecast models (location scorer + timing) from
history already ingested into DATABASE_URL, and persist them so the live API picks them up.

    uv run python scripts/train.py [--as-of ISO_DATETIME] [--model-dir models]

Without --as-of, trains on everything ingested so far (the latest ingest batch's own sim_time).
Prints the resulting version ids and row counts. If there isn't enough data yet
(policy.forecast.timing.n_min unmet, or zero labelled complaint/candidate pairs), says so and
still writes a model file for the scorer once there's at least one training row — a truly empty
run raises rather than silently persisting a useless model.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

from nakabandi.forecast.application.train import TrainModels
from nakabandi.forecast.infrastructure.model_store import ModelStore
from nakabandi.forecast.infrastructure.training_data import SqlTrainingDataPort
from nakabandi.geo import GeoService
from nakabandi.graph import ClusterService
from nakabandi.graph.infrastructure.repositories import SqlClusterRepo
from nakabandi.intake import LienContextLookup, latest_ingest_sim_time
from nakabandi.shared import EventBus, Policy, get_settings
from nakabandi.shared.infrastructure.db import create_sqlite_engine, make_session_factory


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--as-of", type=str, default=None, help="ISO datetime; default: latest ingest"
    )
    parser.add_argument("--model-dir", type=str, default="models")
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
            print("train: no data ingested yet (DATABASE_URL is empty) — nothing to train on.")
            return 1

        data_port = SqlTrainingDataPort(
            cluster_service=ClusterService(SqlClusterRepo(session), EventBus()),
            lien_lookup=LienContextLookup(session),
            geo_service=GeoService(session),
            policy=policy,
        )
        model_store = ModelStore(args.model_dir)
        result = TrainModels(data_port, model_store, policy).run(as_of_end)

    print(
        f"train: as_of={as_of_end.isoformat()} "
        f"train_rows={result.training_rows} val_rows={result.val_rows} "
        f"elapsed_s={result.elapsed_s:.2f}"
    )
    print(f"train: scorer_id={result.scorer_id} timing_id={result.timing_id}")
    if result.training_rows == 0:
        print(
            "train: WARNING — 0 labelled training rows (no complaint yet has both a cluster "
            "and an observed cash-out within its candidate set). The scorer file was written "
            "but is untrained; the live API will keep using the heuristic fallback until "
            "GenerateForecast is given a model_store AND enough resolved complaints exist. "
            "Let world-sim run longer, then re-run this script."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
