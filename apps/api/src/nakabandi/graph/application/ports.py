"""ports.py — Repository abstractions for the graph module (DOC 3 M2).

All methods take `as_of: SimTime` to enforce the LC-2 as-of rule.
These are abstract base classes (ports); SQLAlchemy implementations live in
graph/infrastructure/repositories.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from nakabandi.graph.domain.types import (
    ClusterFootprint,
    LocationStat,
    PointInTimeStats,
)
from nakabandi.shared import Id, SimTime


class ClusterRepo(ABC):
    """Port: reads and writes cluster-level data."""

    @abstractmethod
    def get_cluster_ids_for_accounts(self, account_ids: list[Id]) -> dict[Id, Id]:
        """Return {account_id: cluster_id} for accounts that already have a cluster."""

    @abstractmethod
    def save_cluster(self, cluster_id: Id, created_at: SimTime) -> None:
        """Persist a new cluster record (idempotent on cluster_id)."""

    @abstractmethod
    def reassign_accounts(self, account_ids: list[Id], cluster_id: Id, as_of: SimTime) -> None:
        """Point all given accounts to cluster_id; record membership as_of."""

    @abstractmethod
    def mark_absorbed(self, absorbed_id: Id, surviving_id: Id, as_of: SimTime) -> None:
        """Record that absorbed_id no longer exists (merged into surviving_id)."""

    @abstractmethod
    def get_stats(self, cluster_id: Id, as_of: SimTime) -> PointInTimeStats:
        """Return aggregate stats bounded by as_of."""

    @abstractmethod
    def get_footprint(self, cluster_id: Id, as_of: SimTime) -> ClusterFootprint | None:
        """Return the pre-computed footprint, or None if too few observations."""

    @abstractmethod
    def get_location_stats(
        self, cluster_id: Id, as_of: SimTime, limit: int = 200
    ) -> list[LocationStat]:
        """Return per-location stats bounded by as_of, capped at limit."""

    @abstractmethod
    def save_footprint(
        self, cluster_id: Id, footprint: ClusterFootprint, updated_at: SimTime
    ) -> None:
        """Persist a recomputed footprint (overwrites prior value)."""
