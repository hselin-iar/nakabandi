"""severity() — maps score inputs to Severity bands (DOC 3 M4, LC-7 alerting.severity_bands).

All thresholds come from the injected Policy; never hard-coded here.
"""

from __future__ import annotations

import math

from nakabandi_contracts.enums import Severity, Verdict

from nakabandi.shared import Policy


def severity(
    confidence: float,
    amount_paise: int,
    verdict: Verdict,
    policy: Policy,
) -> Severity:
    """Compute alert severity from forecast and interception inputs.

    DOC 3 M4:
      score = confidence × log1p(amount) × max(interception_probability, floor)

    interception_probability maps from Verdict via policy thresholds:
      INTERCEPTABLE -> policy.interception.thresholds.interceptable
      MARGINAL      -> policy.interception.thresholds.marginal
      NOT_INTERCEPTABLE -> 0.0

    Bands (descending): CRITICAL >= critical threshold, HIGH >= high, MEDIUM >= medium, else LOW.
    """
    thresholds = policy.interception.thresholds
    floor = thresholds.marginal  # minimum probability floor

    verdict_prob: dict[Verdict, float] = {
        Verdict.INTERCEPTABLE: thresholds.interceptable,
        Verdict.MARGINAL: thresholds.marginal,
        Verdict.NOT_INTERCEPTABLE: 0.0,
    }
    interception_p = verdict_prob.get(verdict, 0.0)
    effective_p = max(interception_p, floor)

    score = confidence * math.log1p(amount_paise) * effective_p

    bands = policy.alerting.severity_bands
    if score >= bands.critical:
        return Severity.CRITICAL
    if score >= bands.high:
        return Severity.HIGH
    if score >= bands.medium:
        return Severity.MEDIUM
    return Severity.LOW
