"""A9 unit tests (DOC 3 M3 TESTING PLAN, Unit): bucketing, mass_from_forecast, decayed_intensity,
apply_k_threshold."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from nakabandi.analytics.domain.potential import decayed_intensity
from nakabandi.analytics.domain.rollup import (
    ForecastFacts,
    band_of,
    bucket_hour,
    mass_from_forecast,
)
from nakabandi.analytics.domain.suppress import apply_k_threshold

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def test_bucket_hour_floors_to_the_hour() -> None:
    assert bucket_hour(datetime(2026, 1, 15, 12, 59, 59, 999, tzinfo=UTC)) == NOW


@pytest.mark.parametrize(
    ("value", "band"), [(0, 0), (4_999_999, 0), (5_000_000, 1), (19_999_999, 1), (10**9, 3)]
)
def test_band_of_uses_the_policy_boundaries(value: int, band: int) -> None:
    assert band_of(value, [5_000_000, 20_000_000, 100_000_000]) == band


def test_confidence_bands_are_left_closed() -> None:
    assert [band_of(c, [0.3, 0.6, 0.85]) for c in (0.1, 0.3, 0.59, 0.6, 0.9)] == [0, 1, 1, 2, 3]


def _facts(p120: float = 0.5) -> ForecastFacts:
    return ForecastFacts(
        forecast_id="f",
        complaint_id="c",
        generated_at=NOW,
        confidence=0.7,
        p120=p120,
        cell_items=[("cell-1", 0.75), ("cell-2", 0.25)],
        location_items=[("loc-1", 0.6), ("loc-2", 0.3), ("loc-3", 0.1)],
    )


def test_mass_is_item_probability_times_p120_per_level() -> None:
    items = {(m.target_kind, m.target_id): m.mass for m in mass_from_forecast(_facts(0.5))}
    assert items == pytest.approx(
        {
            ("cell", "cell-1"): 0.375,
            ("cell", "cell-2"): 0.125,
            ("location", "loc-1"): 0.30,
            ("location", "loc-2"): 0.15,
            ("location", "loc-3"): 0.05,
        }
    )


def test_mass_per_level_sums_to_at_most_the_probability_mass() -> None:
    for p120 in (0.0, 0.3, 1.0):
        items = mass_from_forecast(_facts(p120))
        for kind in ("cell", "location"):
            assert sum(m.mass for m in items if m.target_kind == kind) <= p120 + 1e-9


def test_an_abstained_level_has_no_items_so_no_mass() -> None:
    facts = ForecastFacts("f", "c", NOW, 0.5, 0.5, cell_items=[], location_items=[("loc-1", 1.0)])
    assert [m.target_kind for m in mass_from_forecast(facts)] == ["location"]


def test_decayed_intensity_halves_every_half_life() -> None:
    fresh = decayed_intensity([(1.0, NOW)], NOW, lookback_h=72, half_life_h=24)
    day_old = decayed_intensity([(1.0, NOW - timedelta(hours=24))], NOW, 72, 24)
    assert fresh == pytest.approx(1.0) and day_old == pytest.approx(0.5)


def test_decayed_intensity_is_monotone_in_age() -> None:
    values = [
        decayed_intensity([(1.0, NOW - timedelta(hours=h))], NOW, 72, 24) for h in range(0, 73, 6)
    ]
    assert values == sorted(values, reverse=True) and len(set(values)) == len(values)


def test_decayed_intensity_ignores_the_too_old_and_the_future() -> None:
    samples = [
        (1.0, NOW - timedelta(hours=73)),
        (1.0, NOW + timedelta(minutes=1)),
        (2.0, NOW - timedelta(hours=72)),
    ]
    assert decayed_intensity(samples, NOW, 72, 24) == pytest.approx(2.0 * 0.5**3)


@dataclass
class _Cell:
    id: str
    alert_count: int


def test_apply_k_threshold_drops_cells_below_k_and_counts_them() -> None:
    cells = [_Cell("a", 1), _Cell("b", 3), _Cell("c", 2), _Cell("d", 5)]
    kept, suppressed = apply_k_threshold(cells, 3)
    assert [c.id for c in kept] == ["b", "d"] and suppressed == 2


def test_apply_k_threshold_keeps_everything_at_k_one() -> None:
    kept, suppressed = apply_k_threshold([_Cell("a", 1)], 1)
    assert len(kept) == 1 and suppressed == 0
