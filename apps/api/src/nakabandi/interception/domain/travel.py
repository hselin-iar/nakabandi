"""travel.py — TravelTimeEstimator port and HaversineEstimator (DOC 3 M6).

HaversineEstimator.eta_min(unit_km, area_type) -> float
    = unit_km * road_factor / speed_kmh[area_type] * 60
    All three constants read from policy (never hard-coded). DOC 3: AP-10 guard.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from nakabandi.shared import Policy


class TravelTimeEstimator(ABC):
    """Port: any estimator that can convert a distance and area type to minutes."""

    @abstractmethod
    def eta_min(self, distance_km: float, area_type: str) -> float:
        """Estimated travel time in minutes."""


class HaversineEstimator(TravelTimeEstimator):
    """Straight-line + road-factor estimator.

    Formula (DOC 3 M6):
        eta_min = distance_km * road_factor / speed_kmh[area_type] * 60

    Parameters come from policy — never constants in code.
    Unknown area_type falls back to the most conservative (slowest) speed.
    """

    def __init__(self, policy: Policy) -> None:
        self._road_factor: float = policy.interception.road_factor
        self._speed: dict[str, float] = {
            "urban": policy.interception.speed_kmh.urban,
            "semi_urban": policy.interception.speed_kmh.semi_urban,
            "rural": policy.interception.speed_kmh.rural,
        }

    def eta_min(self, distance_km: float, area_type: str) -> float:
        """Estimated travel time in minutes. Falls back to urban (slowest) for unknown types."""
        speed = self._speed.get(area_type, min(self._speed.values()))
        if speed <= 0:
            raise ValueError(f"speed_kmh for {area_type!r} must be > 0, got {speed}")
        return distance_km * self._road_factor / speed * 60
