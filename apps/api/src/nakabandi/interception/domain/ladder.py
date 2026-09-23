"""ladder.py — ladder_level(channel, verdict, confidence, policy) -> LadderLevel (DOC 3 M6).

First matching rule in policy.interception.ladder wins.
'*' in a rule matches any value.
Confidence below policy.interception.min_confidence_for_action => NONE.
Default rule L2 is the catch-all (guaranteed present by PolicyLoadError validation).
"""

from __future__ import annotations

from nakabandi_contracts.enums import LadderLevel, Verdict

from nakabandi.shared import Policy


def ladder_level(
    channel: str,
    verdict: Verdict,
    confidence: float,
    policy: Policy,
) -> LadderLevel:
    """Return the intervention ladder level for this target.

    DOC 3 M6:
      1. If confidence < min_confidence_for_action: return NONE (monitor only).
      2. Walk policy.interception.ladder; return the first matching rule's level.
         A rule matches if rule.channel in {channel, '*'} and rule.verdict in {verdict.value, '*'}.
      3. The catch-all rule (channel='*', verdict='*') is always last —
         guaranteed by policy validation.

    Parameters
    ----------
    channel:
        The cash-out channel string (e.g. "ATM", "BRANCH", "AGENT").
    verdict:
        Verdict from verdict_from().
    confidence:
        Forecast confidence for this target (float in [0, 1]).
    policy:
        The loaded Policy object.
    """
    if confidence < policy.interception.min_confidence_for_action:
        return LadderLevel.NONE

    verdict_str = verdict.value
    for rule in policy.interception.ladder:
        channel_match = rule.channel == "*" or rule.channel == channel
        verdict_match = rule.verdict == "*" or rule.verdict == verdict_str
        if channel_match and verdict_match:
            return rule.level

    # Should never reach here — PolicyLoadError enforces a catch-all.
    return LadderLevel.L2  # defensive fallback
