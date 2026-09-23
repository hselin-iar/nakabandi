"""AcknowledgeAlert use case (DOC 3 M4 — needs Principal; authorises, transitions, saves)."""

from __future__ import annotations

from collections.abc import Mapping, Set

import structlog
from nakabandi_contracts.enums import AlertStatus, Permission, Role

from nakabandi.access import Principal, authorize
from nakabandi.alerting.application.ports import AlertRepo
from nakabandi.alerting.application.scope import scope_of
from nakabandi.alerting.domain.alert import Alert, TimelineEntry
from nakabandi.shared import Clock, NotFound, Policy, new_id

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
        # 1. Authorize the permission
        authorize(principal, Permission.ACKNOWLEDGE, self._role_perms)

        # 2. Load
        alert: Alert | None = self._repo.get_by_id(alert_id)
        if alert is None:
            raise NotFound("ALERT_NOT_FOUND", f"Alert {alert_id!r} not found")

        # 3. Scope check: the alert must lie inside the principal's own scope
        authorize(principal, Permission.ACKNOWLEDGE, self._role_perms, scope_of(alert))

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
