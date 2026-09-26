"""Public facade of the graph module: what other modules may import (DOC 3 M2).

Exports:
  ClusterService   — resolve(), context_for(), rebuild()
  ClusterResolution, ClusterContext  — value objects (read-only by callers)
"""

from __future__ import annotations

import structlog

from nakabandi.graph.application.apply_cashouts import (
    ApplyCashOuts,
    ApplyConfirmedCashOut,
    CashOutFact,
)
from nakabandi.graph.application.ports import ClusterRepo
from nakabandi.graph.application.use_cases import RebuildIndex, RefineCommunities, ResolveCluster
from nakabandi.graph.domain.footprint import compute_footprint
from nakabandi.graph.domain.types import ClusterContext, ClusterResolution
from nakabandi.shared import EventBus, Id, SimTime

logger = structlog.get_logger(__name__)

__all__ = [
    "ClusterService",
    "ClusterContext",
    "ClusterResolution",
    "CashOutFact",
    "compute_footprint",
]


class ClusterService:
    """Façade: the ONLY graph object other modules may import.

    Instantiate once at startup with a repo and bus; pass it into use cases
    and routes via dependency injection.
    """

    def __init__(self, repo: ClusterRepo, bus: EventBus) -> None:
        self._repo = repo
        self._bus = bus
        self._resolve_uc = ResolveCluster(repo, bus)
        self._rebuild_uc = RebuildIndex(repo, bus)
        self._refine_uc = RefineCommunities(repo)
        self._apply_cashouts_uc = ApplyCashOuts(repo, bus)
        self._apply_confirmed_uc = ApplyConfirmedCashOut(repo, bus)

    # ------------------------------------------------------------------
    # M2 public API
    # ------------------------------------------------------------------

    def resolve(self, account_ids: list[Id], as_of: SimTime) -> ClusterResolution:
        """Merge accounts into one cluster; persist; emit events.

        Called by pipeline only.
        """
        return self._resolve_uc.run(account_ids, as_of)

    def context_for(self, cluster_id: Id, as_of: SimTime) -> ClusterContext:
        """Return a snapshot of everything the forecast may see for this cluster.

        All fields are bounded by as_of (LC-2).
        """
        stats = self._repo.get_stats(cluster_id, as_of)
        footprint = self._repo.get_footprint(cluster_id, as_of)
        location_stats = self._repo.get_location_stats(cluster_id, as_of)
        return ClusterContext(
            cluster_id=cluster_id,
            as_of=as_of,
            stats=stats,
            footprint=footprint,
            location_stats=location_stats,
        )

    def rebuild(self, all_account_cluster: dict[Id, Id], as_of: SimTime) -> int:
        """Bulk re-index; returns number of surviving cluster roots."""
        return self._rebuild_uc.run(all_account_cluster, as_of)

    def refine_communities(self, cluster_id: Id, as_of: SimTime) -> None:
        """Annotate sub-communities; never splits or merges."""
        self._refine_uc.run(cluster_id, as_of)

    def cluster_of(self, account_id: Id) -> Id | None:
        """The cluster an account currently belongs to, if any."""
        return self._repo.get_cluster_ids_for_accounts([account_id]).get(account_id)

    def account_ids(self, cluster_id: Id) -> list[Id]:
        """Every account currently in this cluster (casework's build_case, S1)."""
        return self._repo.get_account_ids(cluster_id)

    def all_account_ids(self) -> list[Id]:
        """Every account currently assigned to any cluster (TrainModels' delay_records, B6)."""
        return self._repo.get_all_account_ids()

    def apply_cashouts(self, facts: list[CashOutFact], as_of: SimTime) -> int:
        """Fold observed cash-outs into their clusters' location affinity; returns how many."""
        return self._apply_cashouts_uc.run(facts, as_of)

    def apply_confirmed(
        self, cluster_id: Id, location_id: Id, cell_id: Id, district_id: Id, at: SimTime
    ) -> None:
        """An officer confirmed a cash-out at this location: affinity updates immediately."""
        self._apply_confirmed_uc.run(cluster_id, location_id, cell_id, district_id, at)
