"""use_cases.py — Graph application use cases (DOC 3 M2).

ResolveCluster:    merge accounts, emit ClusterMerged if needed, return ClusterResolution.
RebuildIndex:      bulk re-run of ClusterIndex from all known account-cluster rows.
RefineCommunities: annotate large clusters with Louvain sub-communities (no merge/split).
"""

from __future__ import annotations

import structlog

from nakabandi.graph.application.ports import ClusterRepo
from nakabandi.graph.domain.cluster_index import ClusterIndex
from nakabandi.graph.domain.types import ClusterResolution
from nakabandi.shared import ClusterMerged, ClusterUpdated, EventBus, Id, SimTime, new_id

logger = structlog.get_logger(__name__)


class ResolveCluster:
    """Merge a set of accounts into one cluster; emit events; return resolution.

    Called by pipeline.ProcessComplaint after intake stores the complaint and hops.
    """

    def __init__(self, repo: ClusterRepo, bus: EventBus) -> None:
        self._repo = repo
        self._bus = bus

    def run(
        self,
        account_ids: list[Id],
        as_of: SimTime,
    ) -> ClusterResolution:
        """Resolve accounts to a cluster, persisting any changes.

        Parameters
        ----------
        account_ids:
            layer-1 account plus all known hop accounts for this complaint.
        as_of:
            The sim-clock time at which this resolution takes place (LC-2).
        """
        existing = self._repo.get_cluster_ids_for_accounts(account_ids)
        index = ClusterIndex(existing)
        resolution = index.resolve(account_ids)

        # Persist
        self._repo.save_cluster(resolution.cluster_id, created_at=as_of)
        self._repo.reassign_accounts(account_ids, resolution.cluster_id, as_of)
        for absorbed_id in resolution.merged_from:
            self._repo.mark_absorbed(absorbed_id, resolution.cluster_id, as_of)
            self._bus.publish(
                ClusterMerged(
                    event_id=new_id(),
                    occurred_at=as_of,
                    from_id=absorbed_id,
                    into_id=resolution.cluster_id,
                )
            )

        self._bus.publish(
            ClusterUpdated(
                event_id=new_id(),
                occurred_at=as_of,
                cluster_id=resolution.cluster_id,
            )
        )
        logger.info(
            "graph.resolve",
            cluster_id=resolution.cluster_id,
            merged_from=resolution.merged_from,
            is_new=resolution.is_new,
        )
        return resolution


class RebuildIndex:
    """Bulk-re-resolve all known account-cluster assignments.

    Used after a data migration or when an inconsistency is detected.
    Not called during normal complaint processing.
    """

    def __init__(self, repo: ClusterRepo, bus: EventBus) -> None:
        self._repo = repo
        self._bus = bus

    def run(self, all_account_cluster: dict[Id, Id], as_of: SimTime) -> int:
        """Run a full re-index.  Returns count of clusters after rebuild."""
        index = ClusterIndex(all_account_cluster)
        # Resolve every account once to ensure path compression settles
        roots: set[Id] = set()
        for acc in all_account_cluster:
            cid = index._ds.find(all_account_cluster[acc])  # noqa: SLF001
            roots.add(cid)
        logger.info("graph.rebuild_index", roots=len(roots), as_of=str(as_of))
        return len(roots)


class RefineCommunities:
    """Annotate large clusters with Louvain sub-community labels.

    ANNOTATE ONLY — never merges or splits.  Requires the optional `networkx`
    dependency.  Silently skips if the cluster is too small.
    """

    def __init__(self, repo: ClusterRepo, min_size: int = 10) -> None:
        self._repo = repo
        self._min_size = min_size

    def run(self, cluster_id: Id, as_of: SimTime) -> None:
        """Annotate sub-communities for `cluster_id` if it is large enough."""
        stats = self._repo.get_stats(cluster_id, as_of)
        if stats.unique_accounts < self._min_size:
            return
        try:
            import networkx as nx  # noqa: PLC0415,F401 — optional heavy dep; nx used inside block
        except ImportError:
            logger.warning("graph.refine_communities.networkx_missing")
            return
        # We'd build the graph from location stats and run Louvain here.
        # For now: record that we ran but found nothing useful yet.
        footprint = self._repo.get_footprint(cluster_id, as_of)
        if footprint is None:
            return
        # Placeholder: no sub-community annotation until we have hop-pair data
        logger.info(
            "graph.refine_communities.skipped_no_hop_data",
            cluster_id=cluster_id,
        )
