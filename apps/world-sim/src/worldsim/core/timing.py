"""timing.py — Two-component lognormal mixture for cash-out delay (DOC 3 M1, DOC 2 §2.2).

sample_delay_min(mixture_cfg, rng) -> float

Draws a delay in minutes from the configured mixture. Uses log-space so that:
  - fast component: median ~15 min (Appendix A: range 1–60)
  - slow component: median ~240 min (~4 h; "hours to a day")

The component is selected first by weight, then the lognormal is sampled.
Result is clipped to [1, 10080] minutes (1 min … 1 week) to avoid pathological values.
"""

from __future__ import annotations

import math

import numpy as np

from worldsim.core.config import TimingConfig

_MIN_DELAY_MIN: float = 1.0
_MAX_DELAY_MIN: float = 10_080.0  # 1 week


def sample_delay_min(timing: TimingConfig, rng: np.random.Generator) -> float:
    """Sample one cash-out delay (minutes) from the two-component lognormal mixture."""
    weights = [c.weight for c in timing.mixture]
    idx = int(rng.choice(len(weights), p=weights))
    component = timing.mixture[idx]

    # lognormal parameterised by median (= exp(mu)) and sigma
    mu = math.log(component.lognormal_median_min)
    sigma = component.lognormal_sigma
    delay = math.exp(rng.normal(mu, sigma))
    return float(np.clip(delay, _MIN_DELAY_MIN, _MAX_DELAY_MIN))


def sample_delay_array(timing: TimingConfig, rng: np.random.Generator, n: int) -> np.ndarray:
    """Vectorised version — draw n delays at once (used in hot paths)."""
    weights = np.array([c.weight for c in timing.mixture])
    # select component index for each sample
    component_idx = rng.choice(len(timing.mixture), size=n, p=weights)

    delays = np.empty(n)
    for i, comp in enumerate(timing.mixture):
        mask = component_idx == i
        count = int(mask.sum())
        if count == 0:
            continue
        mu = math.log(comp.lognormal_median_min)
        normals = rng.normal(mu, comp.lognormal_sigma, size=count)
        delays[mask] = np.exp(normals)

    return np.clip(delays, _MIN_DELAY_MIN, _MAX_DELAY_MIN)
