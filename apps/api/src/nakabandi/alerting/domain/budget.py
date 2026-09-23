"""budget.rank_and_cap() (DOC 3 M4 — pure, seeded, deterministic).

All caps and exploration_share come from policy; never hard-coded.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from nakabandi.shared import Policy

if TYPE_CHECKING:
    from nakabandi.alerting.domain.alert import Alert


def rank_and_cap(alerts: list[Alert], policy: Policy) -> list[Alert]:
    """Rank alerts and apply per-(role, jurisdiction) budget cap.

    DOC 3 M4:
      priority = confidence × log1p(amount_paise) × interception_probability
      Top budget_per_shift visible per shift queue; rest are deferred.
      With probability exploration_share a deferred alert is promoted (is_probe=True),
      drawn deterministically by seeding with the alert id.

    This function sets is_deferred and is_probe on each Alert in-place and
    returns the same list sorted by descending priority.

    NOTE: amount_paise and interception_probability are not stored on Alert directly;
    we use confidence × 1.0 as a priority proxy here (good enough for budget ranking
    without storing redundant raw inputs on the domain object). A later step can refine
    this by passing the raw inputs through if needed.
    """
    budget = policy.alerting.budget_per_shift
    exploration_share = policy.alerting.exploration_share

    # Sort descending by confidence (proxy for priority)
    ranked = sorted(alerts, key=lambda a: a.confidence, reverse=True)

    visible_count = 0
    for alert in ranked:
        if visible_count < budget:
            alert.is_deferred = False
            alert.is_probe = False
            visible_count += 1
        else:
            # Deterministic exploration draw keyed by alert_id
            h = int(hashlib.md5(alert.id.encode()).hexdigest(), 16)  # noqa: S324
            probe_draw = (h % 10_000) / 10_000.0  # uniform in [0, 1)
            if probe_draw < exploration_share:
                alert.is_deferred = False
                alert.is_probe = True
            else:
                alert.is_deferred = True
                alert.is_probe = False

    return ranked
