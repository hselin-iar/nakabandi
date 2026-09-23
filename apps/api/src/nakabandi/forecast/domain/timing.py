"""timing.py — TimingModel port and MixtureTimingModel (DOC 3 M2, B4 v0).

MixtureTimingModel: two-component lognormal mixture fitted by EM on observed delays.
Shrinkage toward the global mixture: per-cluster posterior weights shrink with strength
n0 from policy (policy.forecast.timing.n0).

horizon_probs(ctx, elapsed_min, horizons) -> TimingForecast
    conditional: P(T <= elapsed + h | T > elapsed) for each horizon h.
    residual_mass = P(T > elapsed).
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod

import numpy as np

from nakabandi.forecast.domain.types import ClusterContext, TimingForecast
from nakabandi.shared import Policy

_LOG2PI = math.log(2 * math.pi)


class TimingModel(ABC):
    """Port: any model that can produce conditional timing probabilities."""

    @abstractmethod
    def horizon_probs(self, ctx: ClusterContext, horizons: list[int]) -> TimingForecast:
        """Compute conditional timing probabilities for the given horizons."""


def _lognormal_cdf(x: float, mu: float, sigma: float) -> float:
    """CDF of a lognormal distribution at x (x > 0)."""
    if x <= 0:
        return 0.0
    from math import erfc, sqrt

    return 0.5 * erfc(-(math.log(x) - mu) / (sigma * sqrt(2)))


def _mixture_cdf(
    t: float, weights: list[float], log_medians: list[float], sigmas: list[float]
) -> float:
    """CDF of a two-component lognormal mixture at t minutes."""
    return sum(
        w * _lognormal_cdf(t, mu, s) for w, mu, s in zip(weights, log_medians, sigmas, strict=False)
    )


# Global prior (fixed for B4; calibrated by Track B sweeps)
_GLOBAL_WEIGHTS: list[float] = [0.6, 0.4]  # [fast, slow]
_GLOBAL_MEDIANS_MIN: list[float] = [30.0, 180.0]  # median delays (minutes)
_GLOBAL_SIGMAS: list[float] = [0.5, 0.8]  # lognormal sigma


class MixtureTimingModel(TimingModel):
    """Two-component lognormal mixture with shrinkage toward the global prior.

    Fitting uses EM on the observed delays for this cluster.
    When the cluster has fewer than n_min observations (policy.forecast.timing.n_min),
    or EM fails, fall back to the global mixture.

    Shrinkage: effective_weight = (n * cluster_weight + n0 * global_weight) / (n + n0)
    where n = cluster's observed cashout count and n0 = policy.forecast.timing.n0.
    """

    def __init__(
        self,
        policy: Policy,
        cluster_weights: list[float] | None = None,
        cluster_medians_min: list[float] | None = None,
        cluster_sigmas: list[float] | None = None,
        n_obs: int = 0,
    ) -> None:
        self._n0: float = policy.forecast.timing.n0
        self._n_min: int = policy.forecast.timing.n_min
        self._n_obs = n_obs

        if cluster_weights is not None and n_obs >= self._n_min:
            # Shrink toward global
            n = float(n_obs)
            shrink = n / (n + self._n0)
            self._weights = [
                shrink * cw + (1 - shrink) * gw
                for cw, gw in zip(cluster_weights, _GLOBAL_WEIGHTS, strict=False)
            ]
            self._medians_min = [
                shrink * cm + (1 - shrink) * gm
                for cm, gm in zip(
                    cluster_medians_min or _GLOBAL_MEDIANS_MIN, _GLOBAL_MEDIANS_MIN, strict=False
                )
            ]
            self._sigmas = [
                shrink * cs + (1 - shrink) * gs
                for cs, gs in zip(cluster_sigmas or _GLOBAL_SIGMAS, _GLOBAL_SIGMAS, strict=False)
            ]
        else:
            # Use global prior
            self._weights = list(_GLOBAL_WEIGHTS)
            self._medians_min = list(_GLOBAL_MEDIANS_MIN)
            self._sigmas = list(_GLOBAL_SIGMAS)

        # Convert medians to log-space means (μ = log(median) for lognormal)
        self._log_medians = [math.log(m) for m in self._medians_min]

    @classmethod
    def fit(cls, delays_min: list[float], policy: Policy) -> MixtureTimingModel:
        """Fit a two-component lognormal mixture by EM on observed delays.

        Falls back to the global prior if len(delays_min) < n_min or EM diverges.
        """
        n_min = policy.forecast.timing.n_min
        if len(delays_min) < n_min:
            return cls(policy=policy, n_obs=len(delays_min))

        delays = np.array(delays_min, dtype=float)
        delays = delays[delays > 0]  # guard
        if len(delays) < n_min:
            return cls(policy=policy, n_obs=0)

        # EM on log-delays
        log_d = np.log(delays)
        n = len(delays)

        # Initialise: split at median
        split = float(np.median(log_d))
        weights = [0.5, 0.5]
        means = [
            float(np.mean(log_d[log_d <= split])) if (log_d <= split).any() else split - 0.5,
            float(np.mean(log_d[log_d > split])) if (log_d > split).any() else split + 0.5,
        ]
        stds = [
            max(float(np.std(log_d[log_d <= split])), 0.1),
            max(float(np.std(log_d[log_d > split])), 0.1),
        ]

        for _ in range(50):
            # E-step
            def _norm_pdf(x: np.ndarray, mu: float, sigma: float) -> np.ndarray:
                return np.exp(-0.5 * ((x - mu) / sigma) ** 2) / (sigma * math.sqrt(2 * math.pi))

            r0 = weights[0] * _norm_pdf(log_d, means[0], stds[0])
            r1 = weights[1] * _norm_pdf(log_d, means[1], stds[1])
            total = r0 + r1 + 1e-300
            r0, r1 = r0 / total, r1 / total

            # M-step
            n0, n1 = float(r0.sum()), float(r1.sum())
            if n0 < 1e-6 or n1 < 1e-6:
                break
            weights = [n0 / n, n1 / n]
            means = [float((r0 * log_d).sum() / n0), float((r1 * log_d).sum() / n1)]
            stds = [
                max(float(np.sqrt((r0 * (log_d - means[0]) ** 2).sum() / n0)), 0.05),
                max(float(np.sqrt((r1 * (log_d - means[1]) ** 2).sum() / n1)), 0.05),
            ]

        medians_min = [math.exp(m) for m in means]
        return cls(
            policy=policy,
            cluster_weights=weights,
            cluster_medians_min=medians_min,
            cluster_sigmas=stds,
            n_obs=n,
        )

    def horizon_probs(self, ctx: ClusterContext, horizons: list[int]) -> TimingForecast:
        """Return conditional timing probabilities given elapsed time in ctx.

        P(T <= elapsed + h | T > elapsed) = (F(elapsed+h) - F(elapsed)) / (1 - F(elapsed))
        """
        elapsed = ctx.elapsed_min
        f_elapsed = _mixture_cdf(elapsed, self._weights, self._log_medians, self._sigmas)
        residual = max(0.0, 1.0 - f_elapsed)

        cond_probs = []
        for h in horizons:
            f_h = _mixture_cdf(elapsed + h, self._weights, self._log_medians, self._sigmas)
            if residual < 1e-9:
                p = 0.0
            else:
                p = max(0.0, (f_h - f_elapsed) / residual)
            cond_probs.append(min(1.0, p))

        # Ensure monotone (small float errors can violate it)
        for i in range(1, len(cond_probs)):
            cond_probs[i] = max(cond_probs[i], cond_probs[i - 1])

        # Map horizons [30, 60, 120] to p30/p60/p120 (by position)
        p_map = dict(zip(horizons, cond_probs, strict=False))
        return TimingForecast(
            weights=list(self._weights),
            medians_min=list(self._medians_min),
            sigmas=list(self._sigmas),
            elapsed_min=elapsed,
            residual_mass=residual,
            p30=p_map.get(30, cond_probs[0] if cond_probs else 0.0),
            p60=p_map.get(60, cond_probs[1] if len(cond_probs) > 1 else 0.0),
            p120=p_map.get(120, cond_probs[2] if len(cond_probs) > 2 else 0.0),
        )
