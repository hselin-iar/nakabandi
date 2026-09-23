"""ports.py — Repository abstractions for the interception module (DOC 3 M6)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from nakabandi.interception.domain.types import InterceptAssessment
from nakabandi.interception.domain.units import Unit
from nakabandi.shared import Id, SimTime


class UnitRepo(ABC):
    """Port: reads law-enforcement unit data."""

    @abstractmethod
    def all_units(self) -> list[Unit]:
        """Return all registered units that have a valid position."""


class AssessmentRepo(ABC):
    """Port: persists interception assessments."""

    @abstractmethod
    def save(self, assessment: InterceptAssessment, as_of: SimTime) -> None:
        """Persist an assessment (idempotent on assessment.id)."""

    @abstractmethod
    def get_by_forecast(self, forecast_id: Id) -> list[InterceptAssessment]:
        """Return all assessments derived from the given forecast."""
