"""probability.py — interception_probability(eta_min, timing) -> float (DOC 3 M6).

= 1 - F_resid(eta_min) : the probability that the cash-out has NOT yet happened
when the unit arrives, using the conditional mixture from the forecast.

timing.residual_mass is P(T > elapsed). The conditional CDF at eta_min is:
    F_cond(eta) = (F(elapsed + eta) - F(elapsed)) / P(T > elapsed)

but TimingForecast already pre-computes p30, p60, p120 as conditional probabilities
(P(T <= elapsed + h | T > elapsed)), so we interpolate from those breakpoints.

For eta beyond p120 we extrapolate linearly towards 1 using the last two points,
capped at 1. For eta_min <= 0 the cash-out is assumed to have not yet happened
(probability = 0; interception is trivially possible).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TimingForecast:
    """Minimal timing view needed by the interception domain.

    Mirrors the shape of nakabandi_contracts.ingest.Tick timing dict;
    kept as a pure domain dataclass so the domain has no contract dependency.
    """

    residual_mass: float
    """P(T > elapsed) — how much probability mass remains."""
    p30: float
    """P(T <= elapsed+30 min | T > elapsed)."""
    p60: float
    """P(T <= elapsed+60 min | T > elapsed)."""
    p120: float
    """P(T <= elapsed+120 min | T > elapsed)."""


def interception_probability(eta_min: float, timing: TimingForecast) -> float:
    """Probability that a unit arriving in eta_min minutes intercepts the cash-out.

    = P(T > elapsed + eta | T > elapsed)
    = 1 - P(T <= elapsed + eta | T > elapsed)
    = 1 - F_cond(eta)

    Uses piecewise linear interpolation over (0, p30, p60, p120).

    Parameters
    ----------
    eta_min:
        Estimated unit travel time in minutes (>= 0).
    timing:
        Conditional timing probabilities from the forecast.

    Returns
    -------
    float in [0, 1]. 0 means the cash-out has almost certainly already happened;
    1 means there is almost certainly still time.
    """
    if eta_min < 0:
        return float(timing.residual_mass)

    # Breakpoints: (horizon_min, conditional_cdf_value)
    breakpoints = [(0.0, 0.0), (30.0, timing.p30), (60.0, timing.p60), (120.0, timing.p120)]

    # Find the interval containing eta_min
    for i in range(len(breakpoints) - 1):
        t_lo, f_lo = breakpoints[i]
        t_hi, f_hi = breakpoints[i + 1]
        if t_lo <= eta_min <= t_hi:
            # Linear interpolation
            frac = (eta_min - t_lo) / (t_hi - t_lo) if t_hi > t_lo else 0.0
            f_cond = f_lo + frac * (f_hi - f_lo)
            return max(0.0, 1.0 - f_cond)

    # eta_min > 120: extrapolate linearly from the last two breakpoints
    t_lo, f_lo = breakpoints[-2]
    t_hi, f_hi = breakpoints[-1]
    slope = (f_hi - f_lo) / (t_hi - t_lo) if t_hi > t_lo else 0.0
    f_extrap = f_hi + slope * (eta_min - t_hi)
    f_capped = min(1.0, f_extrap)
    return max(0.0, 1.0 - f_capped)
