"""k-threshold suppression (DOC 3 M3 domain/suppress.py; DOC 1 §1.5 privacy)."""

from __future__ import annotations

from typing import Protocol, TypeVar


class _Counted(Protocol):
    @property
    def alert_count(self) -> int: ...


T = TypeVar("T", bound=_Counted)


def apply_k_threshold(cells: list[T], k: int) -> tuple[list[T], int]:
    """Drop every cell with fewer than `k` contributing alerts and say how many were dropped. The
    caller applies this ABOVE location level only: a single location is shown as it is."""
    kept = [c for c in cells if c.alert_count >= k]
    return kept, len(cells) - len(kept)
