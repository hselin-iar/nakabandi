"""disjoint_set.py — Union-Find with path compression and union by size (DOC 3 M2).

Rules (enforced by DOC 3):
  - Path compression + union by size: amortised O(α) per operation.
  - Deterministic tie-break: when two roots have equal size the OLDER (lexicographically
    smaller ULID) cluster id survives.  Clusters never split (post-MVP).
  - Every merge emits a MergeResult; callers decide whether to raise ClusterMerged.
  - Pure Python / no I/O. Takes no as_of; as_of is a read-model concern (ClusterIndex).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MergeResult:
    """Outcome of a union operation.

    surviving_id: the cluster id that persists.
    absorbed_id:  the cluster id that no longer exists (all members moved).
    was_new:      True if one of the two sides was brand-new (size == 1).
    """

    surviving_id: str
    absorbed_id: str
    was_new: bool


class DisjointSet:
    """Thread-unsafe (single-process) union-find over cluster ids (str ULIDs).

    Example
    -------
    >>> ds = DisjointSet()
    >>> ds.add("A"); ds.add("B"); ds.add("C")
    >>> r = ds.union("A", "B")
    >>> ds.find("A") == ds.find("B")
    True
    """

    def __init__(self) -> None:
        self._parent: dict[str, str] = {}
        self._size: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, x: str) -> None:
        """Register a new singleton cluster.  No-op if already known."""
        if x not in self._parent:
            self._parent[x] = x
            self._size[x] = 1

    def find(self, x: str) -> str:
        """Return the canonical root of x's component (path-compressed)."""
        if x not in self._parent:
            raise KeyError(f"DisjointSet: unknown element {x!r}")
        # Path compression (iterative, no recursion limit risk)
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        # Compress
        node = x
        while self._parent[node] != root:
            nxt = self._parent[node]
            self._parent[node] = root
            node = nxt
        return root

    def union(self, a: str, b: str) -> MergeResult | None:
        """Merge the components containing *a* and *b*.

        Returns a MergeResult if the two were in different components, or
        None if they were already together (idempotent, safe to call twice).
        """
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return None  # already united
        sa, sb = self._size[ra], self._size[rb]
        # Union by size with deterministic tie-break (smaller ULID survives)
        if sa > sb or (sa == sb and ra < rb):
            survivor, absorbed = ra, rb
        else:
            survivor, absorbed = rb, ra
        self._parent[absorbed] = survivor
        self._size[survivor] = sa + sb
        del self._size[absorbed]
        was_new = sa == 1 or sb == 1
        return MergeResult(surviving_id=survivor, absorbed_id=absorbed, was_new=was_new)

    def size(self, x: str) -> int:
        """Return the number of elements in x's component."""
        return self._size[self.find(x)]

    def __contains__(self, x: str) -> bool:
        return x in self._parent

    def roots(self) -> set[str]:
        """Return the set of all current roots (unique components)."""
        return {v for v in self._parent if self._parent[v] == v}
