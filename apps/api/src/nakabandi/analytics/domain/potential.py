"""The potential layer's intensity (DOC 3 M3 domain/potential.py).

It is a PERSISTENCE ESTIMATE of recent forecast intensity over the next 72 h: recent forecast mass,
exponentially decayed with age. It is not a separate model, and the legend says so."""

from __future__ import annotations

from collections.abc import Iterable

from nakabandi.analytics.domain.rollup import hours_between
from nakabandi.shared import SimTime


def decayed_intensity(
    samples: Iterable[tuple[float, SimTime]],
    now: SimTime,
    lookback_h: float,
    half_life_h: float,
) -> float:
    """Sum of mass * 0.5 ** (age / half_life) over samples no older than `lookback_h`. A sample
    in the future of `now` is not yet known and is ignored. Monotone: the same mass counts for
    less the older it is."""
    total = 0.0
    for mass, at in samples:
        age = hours_between(now, at)
        if age < 0 or age > lookback_h:
            continue
        total += mass * 0.5 ** (age / half_life_h)
    return total
