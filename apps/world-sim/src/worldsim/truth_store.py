"""truth_store.py — world.db repository (truth, runs) (DOC 3 M1 B5).

world.db is a SEPARATE SQLite from the API database; the API process NEVER reads it.
Only world-sim writes it; only the oracle API (never routed) reads it.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa

from worldsim.core.generator import CashOutTruth, ComplaintTruth

_UTC = UTC
_metadata = sa.MetaData()

_runs_table = sa.Table(
    "runs",
    _metadata,
    sa.Column("run_id", sa.String, primary_key=True),
    sa.Column("seed", sa.Integer, nullable=False),
    sa.Column("scenario", sa.String, nullable=False, default="free"),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("status", sa.String, nullable=False, default="running"),
)

_truth_table = sa.Table(
    "truth_events",
    _metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("run_id", sa.String, nullable=False, index=True),
    sa.Column("kind", sa.String, nullable=False),  # complaint | hop | cashout
    sa.Column("external_ref", sa.String, nullable=True, index=True),
    sa.Column("cluster_id", sa.String, nullable=True),
    sa.Column("is_innocent", sa.Boolean, nullable=False, default=False),
    sa.Column("event_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("payload_json", sa.Text, nullable=False),
)

_clusters_table = sa.Table(
    "live_clusters",
    _metadata,
    sa.Column("cluster_id", sa.String, primary_key=True),
    sa.Column("run_id", sa.String, nullable=False),
    sa.Column("injected_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("district_id", sa.String, nullable=False),
    sa.Column("size", sa.Integer, nullable=False),
    sa.Column("fast_weight", sa.Float, nullable=False),
    sa.Column("locality", sa.String, nullable=False),
)


def _frac_day_to_dt(frac_day: float, base_year: int = 2025) -> datetime:
    """Convert fractional day (0.0 = Jan 1 00:00) to UTC datetime."""
    from datetime import timedelta

    origin = datetime(base_year, 1, 1, tzinfo=_UTC)
    return origin + timedelta(days=frac_day)


class TruthStore:
    """Wraps world.db and exposes write + oracle-read methods.

    The live runner writes; the oracle API reads. The API server NEVER imports this.
    """

    def __init__(self, db_path: str | Path = "world.db") -> None:
        self._engine = sa.create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        _metadata.create_all(self._engine)

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    def begin_run(self, run_id: str, seed: int, scenario: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                sa.insert(_runs_table).values(
                    run_id=run_id,
                    seed=seed,
                    scenario=scenario,
                    started_at=datetime.now(_UTC),  # noqa: TID251 — world-sim infra, no injected Clock
                    status="running",
                )
            )

    def end_run(self, run_id: str, status: str = "done") -> None:
        with self._engine.begin() as conn:
            conn.execute(
                sa.update(_runs_table)
                .where(_runs_table.c.run_id == run_id)
                .values(ended_at=datetime.now(_UTC), status=status)  # noqa: TID251
            )

    def reset(self) -> None:
        """Wipe all truth data (used by /control/reset)."""
        with self._engine.begin() as conn:
            conn.execute(sa.delete(_truth_table))
            conn.execute(sa.delete(_clusters_table))
            conn.execute(sa.delete(_runs_table))

    # ------------------------------------------------------------------
    # Truth write
    # ------------------------------------------------------------------

    def save_complaints(
        self, run_id: str, complaints: list[ComplaintTruth], event_at: datetime
    ) -> None:
        if not complaints:
            return
        with self._engine.begin() as conn:
            conn.execute(
                sa.insert(_truth_table),
                [
                    {
                        "run_id": run_id,
                        "kind": "complaint",
                        "external_ref": c.external_ref,
                        "cluster_id": c.cluster_id,
                        "is_innocent": c.is_innocent,
                        "event_at": event_at,
                        "payload_json": json.dumps(
                            {
                                "external_ref": c.external_ref,
                                "cluster_id": c.cluster_id,
                                "is_innocent": c.is_innocent,
                            }
                        ),
                    }
                    for c in complaints
                ],
            )

    def save_cashouts(self, run_id: str, cashouts: list[CashOutTruth], event_at: datetime) -> None:
        if not cashouts:
            return
        with self._engine.begin() as conn:
            conn.execute(
                sa.insert(_truth_table),
                [
                    {
                        "run_id": run_id,
                        "kind": "cashout",
                        "external_ref": c.complaint_ref,
                        "cluster_id": c.cluster_id,
                        "is_innocent": False,
                        "event_at": event_at,
                        "payload_json": json.dumps(
                            {
                                "complaint_ref": c.complaint_ref,
                                "cluster_id": c.cluster_id,
                                "location_id": c.location_id,
                                "amount_paise": c.amount_paise,
                                "channel": c.channel,
                            }
                        ),
                    }
                    for c in cashouts
                ],
            )

    def save_cluster(
        self,
        run_id: str,
        cluster_id: str,
        district_id: str,
        size: int,
        fast_weight: float,
        locality: str,
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                sa.insert(_clusters_table)
                .prefix_with("OR IGNORE")
                .values(
                    cluster_id=cluster_id,
                    run_id=run_id,
                    injected_at=datetime.now(_UTC),  # noqa: TID251
                    district_id=district_id,
                    size=size,
                    fast_weight=fast_weight,
                    locality=locality,
                )
            )

    # ------------------------------------------------------------------
    # Oracle read (oracle API only)
    # ------------------------------------------------------------------

    def get_complaint_truth(self, external_ref: str) -> dict | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                sa.select(_truth_table).where(
                    _truth_table.c.external_ref == external_ref,
                    _truth_table.c.kind == "complaint",
                )
            ).first()
        if row is None:
            return None
        return json.loads(row.payload_json)

    def get_cashouts_in_range(self, from_dt: datetime, to_dt: datetime) -> list[dict]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                sa.select(_truth_table).where(
                    _truth_table.c.kind == "cashout",
                    _truth_table.c.event_at >= from_dt,
                    _truth_table.c.event_at <= to_dt,
                )
            ).all()
        return [json.loads(r.payload_json) for r in rows]

    def get_clusters(self, run_id: str) -> list[dict]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                sa.select(_clusters_table).where(_clusters_table.c.run_id == run_id)
            ).all()
        return [
            {
                "cluster_id": r.cluster_id,
                "district_id": r.district_id,
                "size": r.size,
                "fast_weight": r.fast_weight,
                "locality": r.locality,
            }
            for r in rows
        ]
