"""repositories.py — SQLAlchemy implementations of graph ports (DOC 3 M2).

Tables owned by the graph module (DOC 3 LC-10):
  clusters             (id, created_at, absorbed_by, absorbed_at)
  cluster_members      (account_id, cluster_id, assigned_at)
  cluster_location_stats (cluster_id, location_id, cell_id, district_id,
                          observation_count, total_paise, last_observed_at)

as_of filtering is applied to every read (LC-2).
"""

from __future__ import annotations

from datetime import UTC

import sqlalchemy as sa
from sqlalchemy.orm import Session

from nakabandi.graph.application.ports import ClusterRepo
from nakabandi.graph.domain.types import (
    ClusterFootprint,
    LocationStat,
    PointInTimeStats,
)
from nakabandi.shared import Id, SimTime

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

metadata = sa.MetaData()

clusters = sa.Table(
    "clusters",
    metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("absorbed_by", sa.String, nullable=True),
    sa.Column("absorbed_at", sa.DateTime(timezone=True), nullable=True),
)

cluster_members = sa.Table(
    "cluster_members",
    metadata,
    sa.Column("account_id", sa.String, primary_key=True),
    sa.Column("cluster_id", sa.String, nullable=False, index=True),
    sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
)

cluster_location_stats = sa.Table(
    "cluster_location_stats",
    metadata,
    sa.Column("cluster_id", sa.String, nullable=False, index=True),
    sa.Column("location_id", sa.String, nullable=False),
    sa.Column("cell_id", sa.String, nullable=False),
    sa.Column("district_id", sa.String, nullable=False),
    sa.Column("observation_count", sa.Integer, nullable=False, default=0),
    sa.Column("total_paise", sa.BigInteger, nullable=False, default=0),
    sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("cluster_id", "location_id"),
)

cluster_footprints = sa.Table(
    "cluster_footprints",
    metadata,
    sa.Column("cluster_id", sa.String, primary_key=True),
    sa.Column("centroid_lat", sa.Float, nullable=False),
    sa.Column("centroid_lon", sa.Float, nullable=False),
    sa.Column("radius_km", sa.Float, nullable=False),
    sa.Column("top_locations_json", sa.Text, nullable=False, default="[]"),
    sa.Column("sub_communities_json", sa.Text, nullable=False, default="[]"),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

# ---------------------------------------------------------------------------
# Repository implementation
# ---------------------------------------------------------------------------


class SqlClusterRepo(ClusterRepo):
    def __init__(self, session: Session) -> None:
        self._s = session

    def get_cluster_ids_for_accounts(self, account_ids: list[Id]) -> dict[Id, Id]:
        if not account_ids:
            return {}
        rows = self._s.execute(
            sa.select(cluster_members.c.account_id, cluster_members.c.cluster_id).where(
                cluster_members.c.account_id.in_(account_ids)
            )
        ).all()
        return {r.account_id: r.cluster_id for r in rows}

    def get_account_ids(self, cluster_id: Id) -> list[Id]:
        """Every account currently assigned to this cluster (DOC 2 §2.2 table row: cluster_members
        feeds M2, S1 — added for casework's A12 build_case; Track B's own tables, flagged in Track
        A's Learnings as a cross-track Ownership Map touch)."""
        rows = self._s.scalars(
            sa.select(cluster_members.c.account_id).where(
                cluster_members.c.cluster_id == cluster_id
            )
        ).all()
        return sorted(rows)

    def get_all_account_ids(self) -> list[Id]:
        """Every account currently assigned to any cluster, sorted (TrainModels' delay_records)."""
        rows = self._s.scalars(sa.select(cluster_members.c.account_id)).all()
        return sorted(set(rows))

    def save_cluster(self, cluster_id: Id, created_at: SimTime) -> None:
        self._s.execute(
            sa.insert(clusters)
            .values(id=cluster_id, created_at=created_at, absorbed_by=None, absorbed_at=None)
            .prefix_with("OR IGNORE")
        )

    def reassign_accounts(self, account_ids: list[Id], cluster_id: Id, as_of: SimTime) -> None:
        for acc in account_ids:
            self._s.execute(
                sa.insert(cluster_members)
                .values(account_id=acc, cluster_id=cluster_id, assigned_at=as_of)
                .prefix_with("OR REPLACE")
            )

    def mark_absorbed(self, absorbed_id: Id, surviving_id: Id, as_of: SimTime) -> None:
        self._s.execute(
            sa.update(clusters)
            .where(clusters.c.id == absorbed_id)
            .values(absorbed_by=surviving_id, absorbed_at=as_of)
        )

    def get_stats(self, cluster_id: Id, as_of: SimTime) -> PointInTimeStats:
        # Observations bounded by as_of
        stats_row = self._s.execute(
            sa.select(
                sa.func.count().label("obs_count"),
                sa.func.coalesce(sa.func.sum(cluster_location_stats.c.total_paise), 0).label(
                    "total_paise"
                ),
                sa.func.max(cluster_location_stats.c.last_observed_at).label("last_seen"),
            ).where(
                sa.and_(
                    cluster_location_stats.c.cluster_id == cluster_id,
                    cluster_location_stats.c.last_observed_at <= as_of,
                )
            )
        ).one()

        member_count = self._s.execute(
            sa.select(sa.func.count()).where(cluster_members.c.cluster_id == cluster_id)
        ).scalar_one()

        last_seen = stats_row.last_seen
        if last_seen is not None and last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=UTC)

        return PointInTimeStats(
            observation_count=stats_row.obs_count or 0,
            total_paise=int(stats_row.total_paise or 0),
            complaint_count=0,  # populated by intake→graph join in a later step
            unique_accounts=member_count,
            last_seen_at=last_seen,
        )

    def get_footprint(self, cluster_id: Id, as_of: SimTime) -> ClusterFootprint | None:
        import json

        row = self._s.execute(
            sa.select(cluster_footprints).where(cluster_footprints.c.cluster_id == cluster_id)
        ).one_or_none()
        if row is None:
            return None
        return ClusterFootprint(
            centroid_lat=row.centroid_lat,
            centroid_lon=row.centroid_lon,
            radius_km=row.radius_km,
            top_locations=json.loads(row.top_locations_json),
            sub_communities=json.loads(row.sub_communities_json),
        )

    def get_location_stats(
        self, cluster_id: Id, as_of: SimTime, limit: int = 200
    ) -> list[LocationStat]:
        rows = self._s.execute(
            sa.select(cluster_location_stats)
            .where(
                sa.and_(
                    cluster_location_stats.c.cluster_id == cluster_id,
                    cluster_location_stats.c.last_observed_at <= as_of,
                )
            )
            .order_by(cluster_location_stats.c.observation_count.desc())
            .limit(limit)
        ).all()
        return [
            LocationStat(
                location_id=r.location_id,
                cell_id=r.cell_id,
                district_id=r.district_id,
                observation_count=r.observation_count,
                total_paise=int(r.total_paise),
            )
            for r in rows
        ]

    def save_footprint(
        self, cluster_id: Id, footprint: ClusterFootprint, updated_at: SimTime
    ) -> None:
        import json

        self._s.execute(
            sa.insert(cluster_footprints)
            .values(
                cluster_id=cluster_id,
                centroid_lat=footprint.centroid_lat,
                centroid_lon=footprint.centroid_lon,
                radius_km=footprint.radius_km,
                top_locations_json=json.dumps(footprint.top_locations),
                sub_communities_json=json.dumps(footprint.sub_communities),
                updated_at=updated_at,
            )
            .prefix_with("OR REPLACE")
        )

    def record_location_observation(
        self,
        cluster_id: Id,
        location_id: Id,
        cell_id: Id,
        district_id: Id,
        amount_paise: int,
        observed_at: SimTime,
    ) -> None:
        row = self._s.execute(
            sa.select(cluster_location_stats).where(
                cluster_location_stats.c.cluster_id == cluster_id,
                cluster_location_stats.c.location_id == location_id,
            )
        ).one_or_none()
        if row is None:
            self._s.execute(
                sa.insert(cluster_location_stats).values(
                    cluster_id=cluster_id,
                    location_id=location_id,
                    cell_id=cell_id,
                    district_id=district_id,
                    observation_count=1,
                    total_paise=amount_paise,
                    last_observed_at=observed_at,
                )
            )
            return
        # SQLite hands datetimes back naive; they are UTC (LC-2), so compare like with like.
        previous = row.last_observed_at
        if previous.tzinfo is None:
            previous = previous.replace(tzinfo=UTC)
        self._s.execute(
            sa.update(cluster_location_stats)
            .where(
                cluster_location_stats.c.cluster_id == cluster_id,
                cluster_location_stats.c.location_id == location_id,
            )
            .values(
                observation_count=row.observation_count + 1,
                total_paise=int(row.total_paise) + amount_paise,
                last_observed_at=max(previous, observed_at),
            )
        )

    def move_location_stats(self, from_cluster_id: Id, into_cluster_id: Id) -> None:
        rows = self._s.execute(
            sa.select(cluster_location_stats).where(
                cluster_location_stats.c.cluster_id == from_cluster_id
            )
        ).all()
        for row in rows:
            last = row.last_observed_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=UTC)
            existing = self._s.execute(
                sa.select(cluster_location_stats).where(
                    cluster_location_stats.c.cluster_id == into_cluster_id,
                    cluster_location_stats.c.location_id == row.location_id,
                )
            ).one_or_none()
            if existing is None:
                self._s.execute(
                    sa.insert(cluster_location_stats).values(
                        cluster_id=into_cluster_id,
                        location_id=row.location_id,
                        cell_id=row.cell_id,
                        district_id=row.district_id,
                        observation_count=row.observation_count,
                        total_paise=int(row.total_paise),
                        last_observed_at=last,
                    )
                )
            else:
                theirs = existing.last_observed_at
                if theirs.tzinfo is None:
                    theirs = theirs.replace(tzinfo=UTC)
                self._s.execute(
                    sa.update(cluster_location_stats)
                    .where(
                        cluster_location_stats.c.cluster_id == into_cluster_id,
                        cluster_location_stats.c.location_id == row.location_id,
                    )
                    .values(
                        observation_count=existing.observation_count + row.observation_count,
                        total_paise=int(existing.total_paise) + int(row.total_paise),
                        last_observed_at=max(theirs, last),
                    )
                )
        self._s.execute(
            sa.delete(cluster_location_stats).where(
                cluster_location_stats.c.cluster_id == from_cluster_id
            )
        )
