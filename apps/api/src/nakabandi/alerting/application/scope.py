"""The scope an alert sits in, in the shape access.authorize compares against."""

from __future__ import annotations

from nakabandi.access import Scope
from nakabandi.alerting.domain.alert import Alert


def scope_of(alert: Alert) -> Scope:
    """An alert with an unknown scope has None levels, which authorize() treats as outside any
    scoped principal's reach (fail closed); only an unrestricted principal sees it."""
    return Scope(
        state_id=alert.scope_state_id,
        district_id=alert.scope_district_id,
        bank_id=alert.scope_bank_id,
    )
