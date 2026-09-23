"""abstain.py — apply_abstention(levels, policy) -> levels (DOC 3 M2).

A level abstains when its top-item probability < policy.forecast.abstain.min_confidence[level].
Abstained levels have abstained=True and their items cleared.
"""

from __future__ import annotations

from nakabandi_contracts.enums import Resolution

from nakabandi.forecast.domain.types import LevelForecast
from nakabandi.shared import Policy


def apply_abstention(
    levels: dict[str, LevelForecast],
    policy: Policy,
) -> dict[str, LevelForecast]:
    """Return a new dict with abstained flag set where confidence is below threshold.

    DOC 3 M2: "a level abstains when its top probability < min_confidence[level]".
    Abstention is monotone: if a level abstains, finer levels may also abstain
    (location is finer than cell, cell finer than district).
    """
    thresholds = {
        Resolution.DISTRICT.value: policy.forecast.abstain.min_confidence.district,
        Resolution.CELL.value: policy.forecast.abstain.min_confidence.cell,
        Resolution.LOCATION.value: policy.forecast.abstain.min_confidence.location,
    }

    result: dict[str, LevelForecast] = {}
    for key, level in levels.items():
        threshold = thresholds.get(key, 0.0)
        if level.confidence < threshold:
            result[key] = LevelForecast(
                resolution=level.resolution,
                abstained=True,
                confidence=level.confidence,
                items=[],  # cleared when abstained
            )
        else:
            result[key] = level

    return result
