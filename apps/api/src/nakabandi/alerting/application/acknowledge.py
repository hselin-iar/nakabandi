"""AcknowledgeAlert use case (DOC 3 M4 — needs Principal; authorises, transitions, saves)."""

from __future__ import annotations

from collections.abc import Mapping, Set

import structlog
from nakabandi_contracts.enums import AlertStatus, Permission, Role

from nakabandi.access import Principal, authorize
from nakabandi.alerting.application.ports import AlertRepo
from nakabandi.alerting.domain.alert import Alert, TimelineEntry
from nakabandi.shared import Clock, Forbidden, NotFound, Policy, new_id

logger = structlog.get_logger(__name__)


class AcknowledgeAlert:
    """Transition an open or escalated alert → acknowledged.

    DOC 3 M4: "AcknowledgeAlert (needs Principal)".
    Permission required: ACKNOWLEDGE.
    """

    def __init__(
        self,
        alert_repo: AlertRepo,
        policy: Policy,
        clock: Clock,
        role_permissions: Mapping[Role, Set[Permission]],
    ) -> None:
        self._repo = alert_repo
        self._policy = policy
        self._clock = clock
        self._role_perms = role_permissions

    def run(self, principal: Principal, alert_id: str) -> Alert:
        # 1. Authorize
        authorize(principal, Permission.ACKNOWLEDGE, self._role_perms)

        # 2. Load
        alert: Alert | None = self._repo.get_by_id(alert_id)
        if alert is None:
            raise NotFound("ALERT_NOT_FOUND", f"Alert {alert_id!r} not found")

        # 3. Scope check — principal must have visibility of this alert
        if not _scope_allows(principal, alert):
            raise Forbidden("FORBIDDEN_SCOPE", "alert is outside your scope")

        # 4. Transition
        now = self._clock.now()
        entry = TimelineEntry(
            id=new_id(),
            alert_id=alert.id,
            at=now,
            kind="acknowledged",
            actor_id=principal.user_id,
            text_code="alert.acknowledged",
            text_params={"by": principal.display_name},
        )
        alert.transition(AlertStatus.ACKNOWLEDGED, entry)
        self._repo.save(alert)

        logger.info("alerting.acknowledged", alert_id=alert_id, by=principal.user_id)
        return alert


def _scope_allows(principal: Principal, alert: Alert) -> bool:
    """Simple scope check: an unrestricted principal sees everything."""
    scope = principal.scope
    # No scope restrictions set → sees all alerts
    if scope.state_id is None and scope.district_id is None and scope.bank_id is None:
        return True
    # bank_nodal scope: must match the alert's bank reference — not available in A7
    # district scope: not yet mapped on alert in A7 (target_id is a location, not district)
    # For now allow viewing; full scope enforcement lands when geo tables are populated.
    return True
