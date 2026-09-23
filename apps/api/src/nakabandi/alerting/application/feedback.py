"""MarkOutcome and ReviewQueue (DOC 3 S3): the officer feedback loop."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Set

import structlog
from nakabandi_contracts.enums import AlertStatus, Permission, Role

from nakabandi.access import Principal, authorize
from nakabandi.alerting.application.ports import (
    AlertRepo,
    ConfirmedCashOutPort,
    OutcomeRepo,
    TargetScopePort,
)
from nakabandi.alerting.application.scope import scope_of
from nakabandi.alerting.domain.alert import Alert, TimelineEntry
from nakabandi.alerting.domain.outcome import Outcome, OutcomeResult, OutcomeSource
from nakabandi.alerting.domain.uncertainty import order_review_queue
from nakabandi.audit import AuditLog
from nakabandi.shared import Clock, Id, NotFound, Policy, ValidationFailed, new_id

logger = structlog.get_logger(__name__)

# An officer's label closes an alert that was being worked; an open, escalated or expired alert is
# not reopened or force-closed (DOC 3 S3: feedback on an expired alert is allowed for learning and
# does not reopen it).
_CLOSABLE = frozenset({AlertStatus.ACKNOWLEDGED, AlertStatus.ACTIONED})
_CONFIRMS_A_CASHOUT = frozenset({OutcomeResult.HIT, OutcomeResult.LATE})


class MarkOutcome:
    """DOC 3 S3 MarkOutcome.run(principal, alert_id, result, location_id?, reason?)."""

    def __init__(
        self,
        *,
        alert_repo: AlertRepo,
        outcome_repo: OutcomeRepo,
        audit: AuditLog,
        clock: Clock,
        role_permissions: Mapping[Role, Set[Permission]],
        scope_lookup: TargetScopePort | None,
        confirmed: ConfirmedCashOutPort | None,
        on_outcome: Callable[[Alert, Outcome], None] | None = None,
    ) -> None:
        self._alerts = alert_repo
        self._outcomes = outcome_repo
        self._audit = audit
        self._clock = clock
        self._role_perms = role_permissions
        self._scope_lookup = scope_lookup
        self._confirmed = confirmed
        self._on_outcome = on_outcome

    def run(
        self,
        principal: Principal,
        alert_id: Id,
        result: str,
        location_id: Id | None = None,
        reason: str | None = None,
    ) -> tuple[Outcome, bool]:
        """Returns (outcome, created). A repeat of the same (alert, result, location) returns the
        existing row with created=False and does nothing else."""
        authorize(principal, Permission.MARK_OUTCOME, self._role_perms)
        alert = self._alerts.get_by_id(alert_id)
        if alert is None:
            raise NotFound("ALERT_NOT_FOUND", f"Alert {alert_id!r} not found")
        authorize(principal, Permission.MARK_OUTCOME, self._role_perms, scope_of(alert))

        try:
            outcome_result = OutcomeResult(result)
        except ValueError as exc:
            raise ValidationFailed("OUTCOME_INVALID", f"unknown outcome {result!r}") from exc
        if location_id is not None:
            if outcome_result not in _CONFIRMS_A_CASHOUT:
                raise ValidationFailed(
                    "OUTCOME_INVALID", "a location can only be confirmed for a hit or a late hit"
                )
            if self._scope_lookup is None or self._scope_lookup.for_location(location_id) is None:
                raise ValidationFailed(
                    "OUTCOME_LOCATION_UNKNOWN", f"{location_id!r} is not a registry location"
                )

        existing = self._outcomes.find_officer(alert.id, outcome_result.value, location_id)
        if existing is not None:
            return existing, False

        now = self._clock.now()
        outcome = Outcome(
            id=new_id(),
            alert_id=alert.id,
            result=outcome_result.value,
            observation_id=None,
            decided_at=now,
            source=OutcomeSource.OFFICER.value,
            actor_id=principal.user_id,
            location_id=location_id,
            reason=reason,
        )
        self._outcomes.save(outcome)
        self._audit.append(
            actor_id=principal.user_id,
            actor_role=principal.role.value,
            action="outcome.marked",
            entity_type="alert",
            entity_id=alert.id,
            payload={
                "outcome_id": outcome.id,
                "result": outcome.result,
                "location_id": location_id,
            },
            reason=reason,
        )

        # A confirmed cash-out location feeds the graph NOW ("observed_at is always now"), so the
        # cluster's affinity updates without waiting for lagged bank reports.
        if location_id is not None and self._confirmed is not None:
            applied = self._confirmed.apply_confirmed(alert.cluster_ref, location_id, now)
            if not applied:
                logger.warning(
                    "alerting.confirmed_cashout_not_applied",
                    alert_id=alert.id,
                    location_id=location_id,
                )

        alert.timeline.append(
            TimelineEntry(
                id=new_id(),
                alert_id=alert.id,
                at=now,
                kind="outcome",
                actor_id=principal.user_id,
                text_code=f"alert.outcome.{outcome.result}",
                text_params={"source": outcome.source, "by": principal.display_name},
            )
        )
        if alert.status in _CLOSABLE:
            alert.transition(
                AlertStatus.CLOSED,
                TimelineEntry(
                    id=new_id(),
                    alert_id=alert.id,
                    at=now,
                    kind="closed",
                    actor_id=principal.user_id,
                    text_code="alert.closed_by_outcome",
                    text_params={"outcome_id": outcome.id},
                ),
            )
        self._alerts.save(alert)
        if self._on_outcome is not None:
            self._on_outcome(alert, outcome)
        return outcome, True


class ReviewQueue:
    """DOC 3 S3: the alerts an officer has not labelled, most uncertain first, capped at
    policy alerting.review_queue.size."""

    def __init__(self, alert_repo: AlertRepo, policy: Policy) -> None:
        self._alerts = alert_repo
        self._policy = policy

    def run(
        self,
        *,
        state_id: str | None = None,
        district_id: str | None = None,
        bank_id: str | None = None,
    ) -> list[Alert]:
        candidates = self._alerts.list_for_review(
            state_id=state_id, district_id=district_id, bank_id=bank_id
        )
        return order_review_queue(candidates)[: self._policy.alerting.review_queue.size]


__all__ = ["MarkOutcome", "ReviewQueue"]
