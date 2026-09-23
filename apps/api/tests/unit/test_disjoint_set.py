"""test_disjoint_set.py — DisjointSet property and unit tests (DOC 3 M2 Testing Plan).

Properties verified:
  P1. union is commutative: union(a,b) and union(b,a) produce the same root.
  P2. union is idempotent: calling union(a,b) twice doesn't change the root.
  P3. find is stable: repeated find calls return the same value.
  P4. merge yields one component: find(a) == find(b) after union(a,b).
  P5. size is accurate: size equals the number of elements after unions.
  P6. union of disjoint components produces MergeResult.
  P7. union of same component returns None.
  P8. Deterministic tie-break: smaller (lex) ULID survives when sizes are equal.
  P9. bridge-account scenario: accounts sharing a truth cluster resolve to one component.
"""

from __future__ import annotations

import pytest
from nakabandi.graph.domain.disjoint_set import DisjointSet, MergeResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ds(*elements: str) -> DisjointSet:
    ds = DisjointSet()
    for e in elements:
        ds.add(e)
    return ds


# ---------------------------------------------------------------------------
# P1 — union is commutative
# ---------------------------------------------------------------------------


def test_union_commutative_same_root():
    """union(a, b) and union(b, a) on fresh sets yield the same canonical root."""
    ds1 = _ds("A", "B")
    ds2 = _ds("A", "B")
    r1 = ds1.union("A", "B")
    r2 = ds2.union("B", "A")
    assert r1 is not None
    assert r2 is not None
    # Both survivors must be the same element (deterministic tie-break)
    assert r1.surviving_id == r2.surviving_id


# ---------------------------------------------------------------------------
# P2 — union is idempotent
# ---------------------------------------------------------------------------


def test_union_idempotent():
    ds = _ds("A", "B")
    r1 = ds.union("A", "B")
    r2 = ds.union("A", "B")  # already same component
    assert r1 is not None
    assert r2 is None  # second call → None (already together)
    assert ds.find("A") == ds.find("B")


# ---------------------------------------------------------------------------
# P3 — find is stable (path compression doesn't change the root)
# ---------------------------------------------------------------------------


def test_find_stable_after_compression():
    ds = _ds("A", "B", "C")
    ds.union("A", "B")
    ds.union("B", "C")
    root1 = ds.find("A")
    root2 = ds.find("A")  # second call triggers path compression
    assert root1 == root2


def test_find_stable_after_multiple_unions():
    ds = _ds("A", "B", "C", "D")
    ds.union("A", "B")
    ds.union("C", "D")
    ds.union("A", "C")
    for x in ("A", "B", "C", "D"):
        assert ds.find(x) == ds.find("A")


# ---------------------------------------------------------------------------
# P4 — merge yields one component
# ---------------------------------------------------------------------------


def test_merge_yields_one_component():
    ds = _ds("X", "Y", "Z")
    ds.union("X", "Y")
    ds.union("Y", "Z")
    assert ds.find("X") == ds.find("Y") == ds.find("Z")


def test_size_one_component_after_all_unions():
    elements = ["A", "B", "C", "D", "E"]
    ds = _ds(*elements)
    for i in range(len(elements) - 1):
        ds.union(elements[i], elements[i + 1])
    root = ds.find(elements[0])
    assert ds.size(root) == len(elements)
    assert len(ds.roots()) == 1


# ---------------------------------------------------------------------------
# P5 — size accuracy
# ---------------------------------------------------------------------------


def test_size_starts_at_one():
    ds = _ds("A")
    assert ds.size("A") == 1


def test_size_grows_correctly():
    ds = _ds("A", "B", "C")
    ds.union("A", "B")
    assert ds.size(ds.find("A")) == 2
    ds.union("A", "C")
    assert ds.size(ds.find("A")) == 3


def test_size_two_disjoint_components():
    ds = _ds("A", "B", "C", "D")
    ds.union("A", "B")
    ds.union("C", "D")
    assert ds.size(ds.find("A")) == 2
    assert ds.size(ds.find("C")) == 2
    assert len(ds.roots()) == 2


# ---------------------------------------------------------------------------
# P6 — union of disjoint components returns MergeResult
# ---------------------------------------------------------------------------


def test_union_disjoint_returns_merge_result():
    ds = _ds("A", "B")
    result = ds.union("A", "B")
    assert isinstance(result, MergeResult)
    assert result.absorbed_id != result.surviving_id


# ---------------------------------------------------------------------------
# P7 — union of same component returns None
# ---------------------------------------------------------------------------


def test_union_same_component_returns_none():
    ds = _ds("A", "B")
    ds.union("A", "B")
    assert ds.union("A", "B") is None
    assert ds.union("B", "A") is None


# ---------------------------------------------------------------------------
# P8 — deterministic tie-break (lex smaller survives on equal size)
# ---------------------------------------------------------------------------


def test_tie_break_smaller_ulid_survives():
    # Use controlled ids where lex order is clear.
    # "01" < "02" (lex), so "01" should survive when sizes are equal.
    ds = _ds("01AAAAAAAAAAAAAAAAAAAAAAAA", "02AAAAAAAAAAAAAAAAAAAAAAAA")
    result = ds.union("01AAAAAAAAAAAAAAAAAAAAAAAA", "02AAAAAAAAAAAAAAAAAAAAAAAA")
    assert result is not None
    assert result.surviving_id == "01AAAAAAAAAAAAAAAAAAAAAAAA"
    assert result.absorbed_id == "02AAAAAAAAAAAAAAAAAAAAAAAA"


def test_tie_break_commutative():
    """Tie-break is the same regardless of argument order."""
    ds1 = _ds("Z", "A")
    ds2 = _ds("Z", "A")
    r1 = ds1.union("Z", "A")
    r2 = ds2.union("A", "Z")
    assert r1 is not None and r2 is not None
    assert r1.surviving_id == r2.surviving_id == "A"


# ---------------------------------------------------------------------------
# P9 — bridge-account scenario
# ---------------------------------------------------------------------------


def test_bridge_accounts_resolve_to_one_component():
    """Accounts sharing a truth cluster (via bridge) resolve to one component."""
    #
    # Scenario: three mule accounts (M1, M2, M3) where:
    #   - M1 and M2 share cluster C1 (previous resolution)
    #   - M2 and M3 are connected via a new complaint
    #   → after union(M2, M3) all three should resolve to one root
    #
    ds = _ds("C1", "C2")  # C1 = cluster for M1+M2; C2 = new cluster for M3
    ds.union("C1", "C2")
    root = ds.find("C1")
    assert root == ds.find("C2")
    assert ds.size(root) == 2


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_find_unknown_raises():
    ds = DisjointSet()
    with pytest.raises(KeyError):
        ds.find("UNKNOWN")


def test_contains():
    ds = _ds("A")
    assert "A" in ds
    assert "B" not in ds
