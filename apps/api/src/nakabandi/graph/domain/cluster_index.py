"""cluster_index.py — ClusterIndex: resolve accounts to a cluster id (DOC 3 M2).

ClusterIndex is pure domain logic.  It wraps a DisjointSet and a read-only
snapshot of existing account → cluster mappings.  No I/O.

Usage pattern (in application/use_cases.py):
  existing = repo.get_account_clusters(account_ids)   # {account_id: cluster_id}
  index = ClusterIndex(existing)
  resolution = index.resolve(account_ids)
  # then persist: resolution.cluster_id, resolution.merged_from
"""

from __future__ import annotations

from nakabandi.graph.domain.disjoint_set import DisjointSet, MergeResult
from nakabandi.graph.domain.types import ClusterResolution
from nakabandi.shared import Id, new_id


class ClusterIndex:
    """Resolve a set of accounts to one canonical cluster id.

    Parameters
    ----------
    existing_cluster_map:
        Mapping of account_id -> cluster_id for accounts that already have a
        cluster assignment.  Pass an empty dict for a fully-new complaint.
    """

    def __init__(self, existing_cluster_map: dict[Id, Id]) -> None:
        self._account_cluster: dict[Id, Id] = dict(existing_cluster_map)
        self._ds: DisjointSet = DisjointSet()

        # Seed the DisjointSet with all known cluster ids
        for cluster_id in self._account_cluster.values():
            self._ds.add(cluster_id)

    def resolve(self, account_ids: list[Id]) -> ClusterResolution:
        """Union all accounts and return the surviving cluster id.

        Algorithm
        ---------
        1. For accounts with a known cluster, add that cluster to the DS.
        2. For accounts without a cluster, create a fresh cluster id.
        3. Union all the resulting cluster ids.
        4. The surviving root is the canonical cluster id.

        Returns a ClusterResolution with:
          - cluster_id: the surviving root
          - merged_from: all absorbed (now-dead) cluster ids
          - is_new: True if a new cluster was created
        """
        if not account_ids:
            raise ValueError("ClusterIndex.resolve: account_ids must not be empty")

        # Step 1 & 2: map each account to a cluster id
        per_account_cluster: list[Id] = []
        created_new = False
        for acc in account_ids:
            if acc in self._account_cluster:
                cid = self._account_cluster[acc]
            else:
                cid = new_id()
                self._account_cluster[acc] = cid
                self._ds.add(cid)
                created_new = True
            per_account_cluster.append(cid)

        # Step 3: union all cluster ids together
        merged_from: list[Id] = []
        primary = per_account_cluster[0]
        for other in per_account_cluster[1:]:
            result: MergeResult | None = self._ds.union(primary, other)
            if result is not None:
                merged_from.append(result.absorbed_id)
                primary = result.surviving_id  # follow the survivor
            else:
                # already same component — find the root
                primary = self._ds.find(primary)

        surviving = self._ds.find(primary)

        # Step 4: update account→cluster map to point to surviving root
        for acc in account_ids:
            old = self._account_cluster[acc]
            if self._ds.find(old) != old:  # was absorbed
                self._account_cluster[acc] = surviving

        return ClusterResolution(
            cluster_id=surviving,
            merged_from=merged_from,
            is_new=created_new and not merged_from,
        )
