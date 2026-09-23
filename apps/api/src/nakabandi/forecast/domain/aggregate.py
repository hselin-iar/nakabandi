"""aggregate.py — normalise() and aggregate_levels() (DOC 3 M2).

normalise(scores) -> array:     softmax-normalised probabilities summing to 1.
aggregate_levels(probs, cands): builds {LOCATION, CELL, DISTRICT} level forecasts
    by SUMMING child probabilities.  Cell prob = sum of its location probs, etc.
"""

from __future__ import annotations

import numpy as np
from nakabandi_contracts.enums import Resolution

from nakabandi.forecast.domain.types import Candidate, LevelForecast, RankedItem
from nakabandi.shared import Id


def normalise(scores: np.ndarray) -> np.ndarray:
    """Convert raw scores to probabilities via softmax.

    Subtracts max for numerical stability; returns a 1-D array summing to 1 ± 1e-9.
    """
    if len(scores) == 0:
        return np.array([], dtype=float)
    shifted = scores - scores.max()
    exps = np.exp(shifted)
    return exps / exps.sum()


def aggregate_levels(
    probs: np.ndarray,
    candidates: list[Candidate],
) -> dict[str, LevelForecast]:
    """Build LevelForecast for each Resolution by summing child probabilities.

    DOC 3 M2: cell prob = sum of its location probs; district prob = sum of its cell probs.
    Items within each level are sorted by descending prob and ranked 1-based.
    """
    # --- LOCATION level ---
    loc_probs: dict[Id, float] = {}
    for cand, p in zip(candidates, probs, strict=False):
        loc_probs[cand.location_id] = loc_probs.get(cand.location_id, 0.0) + float(p)

    # --- CELL level (sum locations) ---
    cell_probs: dict[Id, float] = {}
    loc_to_cell: dict[Id, Id] = {c.location_id: c.cell_id for c in candidates}
    for loc_id, p in loc_probs.items():
        cell_id = loc_to_cell.get(loc_id, loc_id)
        cell_probs[cell_id] = cell_probs.get(cell_id, 0.0) + p

    # --- DISTRICT level (sum cells) ---
    dist_probs: dict[Id, float] = {}
    cell_to_dist: dict[Id, Id] = {c.cell_id: c.district_id for c in candidates}
    for cell_id, p in cell_probs.items():
        dist_id = cell_to_dist.get(cell_id, cell_id)
        dist_probs[dist_id] = dist_probs.get(dist_id, 0.0) + p

    def _build_level(prob_map: dict[Id, float], resolution: Resolution) -> LevelForecast:
        items = sorted(
            [RankedItem(id=k, prob=v, rank=0) for k, v in prob_map.items()],
            key=lambda x: x.prob,
            reverse=True,
        )
        for rank, item in enumerate(items, start=1):
            item.rank = rank
        # confidence = top-item probability
        confidence = items[0].prob if items else 0.0
        return LevelForecast(
            resolution=resolution,
            abstained=False,
            confidence=confidence,
            items=items,
        )

    return {
        Resolution.LOCATION.value: _build_level(loc_probs, Resolution.LOCATION),
        Resolution.CELL.value: _build_level(cell_probs, Resolution.CELL),
        Resolution.DISTRICT.value: _build_level(dist_probs, Resolution.DISTRICT),
    }
