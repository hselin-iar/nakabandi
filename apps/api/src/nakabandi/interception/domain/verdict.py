"""verdict.py — verdict_from(p, thresholds) -> Verdict (DOC 3 M6).

Thresholds come from policy; never hard-coded.
"""

from __future__ import annotations

from nakabandi_contracts.enums import Verdict

from nakabandi.shared import Policy


def verdict_from(p: float, policy: Policy) -> Verdict:
    """Classify an interception probability into a Verdict.

    DOC 3 M6 rule (starting values in policy.yaml; tunable):
        INTERCEPTABLE     if p >= thresholds.interceptable
        MARGINAL          if p >= thresholds.marginal
        NOT_INTERCEPTABLE otherwise

    Parameters
    ----------
    p:
        interception_probability in [0, 1].
    policy:
        The loaded Policy object — thresholds read from
        policy.interception.thresholds.
    """
    thresholds = policy.interception.thresholds
    if p >= thresholds.interceptable:
        return Verdict.INTERCEPTABLE
    if p >= thresholds.marginal:
        return Verdict.MARGINAL
    return Verdict.NOT_INTERCEPTABLE
