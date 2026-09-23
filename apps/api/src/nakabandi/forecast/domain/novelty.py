"""novelty.py — novelty() and DistrictPrior fallback (DOC 3 M2 B6).

novelty(ctx, policy) -> float in [0, 1]
  A smooth measure of how little we know about a cluster.
  = 1 - tanh(prior_cashout_count / scale)
  0 = well-studied cluster; 1 = completely novel.

DistrictPrior:
  When a cluster is novel (no observed history), fall back to
  district-level empirical frequencies. The prior is a dict keyed
  by district_id -> normalised_weight (sums to 1 across districts).
  Used by GenerateForecast when cluster_size is 0 and no candidates
  can be built from cluster history alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from nakabandi.shared import Id, Policy


def novelty(prior_cashout_count: int, policy: Policy) -> float:
    """Compute novelty score for a cluster.

    Parameters
    ----------
    prior_cashout_count:
        Number of cash-out observations for this cluster up to as_of.
    policy:
        Policy bundle; reads policy.forecast.novelty_threshold (the count at which
        novelty drops to ~0.24, i.e. tanh(1)).

    Returns
    -------
    float in [0, 1], where 1 = completely novel.
    """
    n = float(prior_cashout_count)
    # novelty_threshold is the scale; at n=threshold, tanh(1) ≈ 0.76 → novelty ≈ 0.24
    scale = max(1.0, float(policy.forecast.novelty_threshold))
    return float(1.0 - np.tanh(n / scale))


@dataclass
class DistrictPrior:
    """Empirical district prior: uniform fallback when a cluster is novel.

    The prior is computed from the historical distribution of cash-out
    observations across districts (from the training set). When no observations
    are available, falls back to a uniform distribution over all districts.

    The prior is only used by GenerateForecast when the cluster is so novel
    (no candidates from cluster history or bank footprint) that all levels
    would otherwise abstain.
    """

    # district_id -> weight (sums to 1); populated by TrainModels
    district_weights: dict[str, float] = field(default_factory=dict)

    @classmethod
    def uniform(cls, district_ids: list[str]) -> DistrictPrior:
        """Create a uniform prior over all districts."""
        if not district_ids:
            return cls(district_weights={})
        w = 1.0 / len(district_ids)
        return cls(district_weights={d: w for d in district_ids})

    @classmethod
    def from_counts(cls, district_counts: dict[str, int]) -> DistrictPrior:
        """Build a prior from observed district cash-out counts.

        Smoothed with add-1 (Laplace) so every district has nonzero weight.
        """
        if not district_counts:
            return cls(district_weights={})
        total = sum(district_counts.values()) + len(district_counts)  # Laplace +1
        weights = {d: (count + 1) / total for d, count in district_counts.items()}
        return cls(district_weights=weights)

    def top_districts(self, k: int = 3) -> list[tuple[str, float]]:
        """Return the top-k (district_id, weight) pairs by weight."""
        ranked = sorted(self.district_weights.items(), key=lambda x: -x[1])
        return ranked[:k]

    def weight_for(self, district_id: Id) -> float:
        """Return the prior weight for a district, or uniform if unknown."""
        if not self.district_weights:
            return 0.0
        return self.district_weights.get(district_id, 0.0)
