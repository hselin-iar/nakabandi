"""ports.py — Repository and store abstractions for the forecast module (DOC 3 M2)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

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


class ModelStorePort(ABC):
    """Port: persists and loads trained scorer and timing models.

    The concrete implementation (ModelStore in infrastructure) uses joblib.
    Tests may inject a stub.
    """

    @abstractmethod
    def save_scorer(
        self,
        scorer: Any,
        data_hash: str,
        as_of: SimTime,
        brier_before: float | None = None,
        brier_after: float | None = None,
    ) -> str:
        """Persist scorer. Returns new version_id."""

    @abstractmethod
    def load_scorer(self) -> Any | None:
        """Load scorer from store. Returns None if not yet trained."""

    @abstractmethod
    def save_timing(
        self,
        model: Any,
        data_hash: str,
        as_of: SimTime,
    ) -> str:
        """Persist timing model. Returns new version_id."""

    @abstractmethod
    def load_timing(self) -> Any | None:
        """Load timing model from store. Returns None if not yet trained."""
