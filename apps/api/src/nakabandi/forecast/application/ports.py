"""ports.py — Repository abstractions for the forecast module (DOC 3 M2)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from nakabandi.forecast.domain.types import Forecast
from nakabandi.shared import Id, SimTime


class ForecastRepo(ABC):
    """Port: persists and retrieves Forecast records."""

    @abstractmethod
    def save(self, forecast: Forecast) -> None:
        """Persist a forecast (idempotent on forecast.id)."""

    @abstractmethod
    def get_by_complaint(self, complaint_id: Id, as_of: SimTime) -> Forecast | None:
        """Return the most recent forecast for a complaint generated at or before as_of."""

    @abstractmethod
    def get_latest(self, complaint_id: Id) -> Forecast | None:
        """Return the most recent forecast for a complaint regardless of time."""
