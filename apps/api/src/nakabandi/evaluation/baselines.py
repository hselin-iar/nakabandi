"""baselines.py — Three baseline LocationScorer implementations (DOC 3 B7).

Each baseline implements the LocationScorer port from forecast so it can be
scored through the same evaluation harness as the HGB model.

HotspotBaseline:         score by historical cash-out frequency per location.
NearestToVictimBaseline: score by geographic proximity (closer = higher score).
BankFootprintBaseline:   score by whether the location belongs to the issuing bank.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass
class ScoredLocation:
    """(location_id, score) pair produced by a baseline scorer."""

    location_id: str
    score: float


class HotspotBaseline:
    """Score locations by historical cash-out frequency.

    Locations seen more often in the training set get a higher score.
    Unknown locations get score 0.
    """

    def __init__(self, cashout_counts: dict[str, int]) -> None:
        """
        cashout_counts: mapping from location_id to count of observed cash-outs.
        """
        self._counts = cashout_counts
        total = sum(cashout_counts.values())
        self._total = max(total, 1)

    @classmethod
    def from_cashouts(cls, location_ids: Sequence[str]) -> HotspotBaseline:
        """Build from a flat list of observed cash-out location ids."""
        return cls(dict(Counter(location_ids)))

    def score(self, location_id: str) -> float:
        """Return relative frequency of location_id in the training set."""
        return self._counts.get(location_id, 0) / self._total

    def rank(self, location_ids: Sequence[str]) -> list[str]:
        """Return location_ids sorted by score descending."""
        return sorted(location_ids, key=self.score, reverse=True)


class NearestToVictimBaseline:
    """Score locations by inverse geographic distance from the victim's home.

    score = 1 / (1 + distance_km). Closer = higher score.
    Locations without coordinates get score 0.
    """

    def __init__(self, location_coords: dict[str, tuple[float, float]]) -> None:
        """
        location_coords: mapping from location_id to (lat, lon).
        """
        self._coords = location_coords

    def _haversine_km(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine distance in km between two WGS-84 points."""
        R = 6371.0
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = (
            math.sin(d_lat / 2) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
        )
        return 2 * R * math.asin(math.sqrt(a))

    def score(self, location_id: str, victim_lat: float, victim_lon: float) -> float:
        """Return inverse-distance score for location_id from victim's home."""
        coords = self._coords.get(location_id)
        if coords is None:
            return 0.0
        dist_km = self._haversine_km(victim_lat, victim_lon, coords[0], coords[1])
        return 1.0 / (1.0 + dist_km)

    def rank(self, location_ids: Sequence[str], victim_lat: float, victim_lon: float) -> list[str]:
        """Return location_ids sorted by score descending."""
        return sorted(
            location_ids, key=lambda loc: self.score(loc, victim_lat, victim_lon), reverse=True
        )


class BankFootprintBaseline:
    """Score locations by whether they belong to the issuing bank's ATM / branch network.

    In-network location → score 1.0; outside → score 0.0.
    """

    def __init__(self, bank_location_ids: set[str]) -> None:
        """
        bank_location_ids: set of location_ids that belong to the issuing bank.
        """
        self._bank_locs = bank_location_ids

    @classmethod
    def from_bank_code(cls, all_locations: Sequence[str], bank_code: str) -> BankFootprintBaseline:
        """Build by filtering locations whose id starts with bank_code."""
        return cls({loc for loc in all_locations if loc.startswith(bank_code)})

    def score(self, location_id: str) -> float:
        """1.0 if in-network, 0.0 otherwise."""
        return 1.0 if location_id in self._bank_locs else 0.0

    def rank(self, location_ids: Sequence[str]) -> list[str]:
        """Return location_ids sorted by score descending (in-network first)."""
        return sorted(location_ids, key=self.score, reverse=True)
