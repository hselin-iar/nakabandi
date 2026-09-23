"""Rollup keys and forecast mass (DOC 3 M3 domain/rollup.py). Pure: no I/O, no clock."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from nakabandi.shared import Id, SimTime


def bucket_hour(t: SimTime) -> SimTime:
    """Floor a sim time to the start of its hour (the rollup's time key)."""
    return t.replace(minute=0, second=0, microsecond=0)


def band_of(value: float, boundaries: list[float] | list[int]) -> int:
    """How many policy boundaries `value` has reached: 0 below the first, len(boundaries) at or
    above the last. Used for amount bands (paise) and confidence bands; the boundaries come from
    policy.yaml (heatmap.amount_bands / heatmap.confidence_bands), never from code."""
    return sum(1 for b in boundaries if value >= b)


@dataclass(frozen=True, slots=True)
class ForecastFacts:
    """What the projector needs from a forecast, in analytics' own terms (the adapter in main.py
    copies it out of the forecast module, so analytics never imports forecast internals)."""

    forecast_id: Id
    complaint_id: Id
    generated_at: SimTime
    confidence: float
    p120: float  # timing.p120: P(cash-out within the next two hours)
    cell_items: list[tuple[Id, float]] = field(default_factory=list)  # (cell id, prob)
    location_items: list[tuple[Id, float]] = field(default_factory=list)  # (location id, prob)


@dataclass(frozen=True, slots=True)
class MassItem:
    target_kind: str  # "cell" | "location"
    target_id: Id
    mass: float


def mass_from_forecast(facts: ForecastFacts) -> list[MassItem]:
    """Expected mass per target = item probability x timing.p120 (the next two hours), for every
    level the forecast has (an abstained level contributes no items). Item probabilities sum to 1
    within a level, so a level's mass sums to at most p120 <= 1."""
    items = [MassItem("cell", i, p * facts.p120) for i, p in facts.cell_items]
    items += [MassItem("location", i, p * facts.p120) for i, p in facts.location_items]
    return items


def hours_between(later: SimTime, earlier: SimTime) -> float:
    return (later - earlier) / timedelta(hours=1)
