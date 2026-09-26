"""global_stats.py — GlobalCashoutIndex: as-of, cross-cluster cash-out density (pure, no I/O).

PointInTimeStats (training.py) answers "what did THIS cluster's history look like as of t".
GlobalCashoutIndex answers the same as-of question but unscoped by cluster — the global
empirical base-rate signal HotspotBaseline uses, which hgb_v2 previously lacked (see
docs/state/track-b.md [NEXT_ACTION]). The infrastructure layer fetches the raw
(location_id, observed_at) rows (I/O); replaying them into as-of snapshots is pure domain logic.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GlobalCashoutSnapshot:
    """Global cash-out counts strictly as-of a given timestamp."""

    location_counts: dict[str, int]
    total: int


class GlobalCashoutIndex:
    """Replays a flat list of cash-out observations, sorted by observed_at.

    Usage:
        index = GlobalCashoutIndex(all_cashout_events)  # [(location_id, observed_at), ...]
        snap = index.snapshot_at(as_of)  # strictly observed_at <= as_of (LC-2)
    """

    def __init__(self, events: Sequence[tuple[str, datetime]]) -> None:
        ordered = sorted(events, key=lambda e: e[1])
        self._location_ids: list[str] = [loc_id for loc_id, _ in ordered]
        self._timestamps: list[datetime] = [ts for _, ts in ordered]

    def snapshot_at(self, as_of: datetime) -> GlobalCashoutSnapshot:
        """Return counts for observations with observed_at <= as_of (inclusive, LC-2)."""
        cutoff = bisect_right(self._timestamps, as_of)
        counts = Counter(self._location_ids[:cutoff])
        return GlobalCashoutSnapshot(location_counts=dict(counts), total=cutoff)
