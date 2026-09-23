"""RecordAction: the human gate (DOC 3 M4; DOC 2 §2.1 invariant 7).

Nothing outside this use case can create a hold_request delivery: EnqueueDeliveries takes the
Action this use case just created, and the deliveries table refuses a hold_request row without an
action_id.
"""

from __future__ import annotations

from collections.abc import Mapping, Set
from dataclasses import dataclass, field

import structlog
from nakabandi_contracts.enums import ActionType, AlertStatus, Permission, Role

from nakabandi.access import Principal, authorize
from nakabandi.alerting.application.outbox import EnqueueDeliveries
from nakabandi.alerting.application.ports import (
    ActionRepo,
    AlertRepo,
    LienContextPort,
    LienValidator,
)
from nakabandi.alerting.domain.action import Action, ActionStatus, permission_for
from nakabandi.alerting.domain.alert import Alert, TimelineEntry
from nakabandi.audit import AuditLog
from nakabandi.shared import (
    Clock,
    Conflict,
    Forbidden,
    NotFound,
    SimTime,
    ValidationFailed,
    new_id,
)

logger = structlog.get_logger(__name__)

_ACTIONABLE = frozenset({AlertStatus.OPEN, AlertStatus.ESCALATED, AlertStatus.ACKNOWLEDGED})


@dataclass(frozen=True, slots=True)
class ActionIn:
    """LC-4 ActionIn: { type, reason (required for override; recommended otherwise), params }."""

    type: ActionType
    reason: str | None = None
    params: dict = field(default_factory=dict)


class RecordAction:
    def __init__(
        self,
        *,
        alert_repo: AlertRepo,
        action_repo: ActionRepo,
        enqueue: EnqueueDeliveries,
        audit: AuditLog,
        clock: Clock,
        role_permissions: Mapping[Role, Set[Permission]],
        lien_context: LienContextPort | None,
        validate_lien: LienValidator | None,
    ) -> None:
        self._alerts = alert_repo
        self._actions = action_repo
        self._enqueue = enqueue
        self._audit = audit
        self._clock = clock
        self._role_perms = role_permissions
        self._lien_context = lien_context
        self._validate_lien = validate_lien

    def run(self, principal: Principal, alert_id: str, action_in: ActionIn) -> Action:
        # 1. authorize; a denial is audited before it is re-raised (DOC 3 M4 edge case: "403,
        #    audited as denied"). The caller commits the unit of work so the entry survives.
        try:
            authorize(principal, permission_for(action_in.type), self._role_perms)
        except Forbidden:
            self._audit.append(
                actor_id=principal.user_id,
                actor_role=principal.role.value,
                action="action.denied",
                entity_type="alert",
                entity_id=alert_id,
                payload={"type": action_in.type.value},
                reason=action_in.reason,
            )
            raise

        # 2. load the alert and check its state
        alert: Alert | None = self._alerts.get_by_id(alert_id)
        if alert is None:
            raise NotFound("ALERT_NOT_FOUND", f"Alert {alert_id!r} not found")
        if alert.status not in _ACTIONABLE:
            raise Conflict(
                "INVALID_TRANSITION",
                f"Cannot record an action on an alert that is {alert.status.value!r}",
                details=[{"from": alert.status.value, "to": AlertStatus.ACTIONED.value}],
            )

        now = self._clock.now()

        # 3. type-specific validation
        params = dict(action_in.params)
        hold: _HoldRequest | None = None
        if action_in.type is ActionType.REQUEST_HOLD:
            hold = self._validate_hold(params, now)
            params = {
                "account_id": hold.account_id,
                "proposed_paise": hold.proposed_paise,
                "complaint_id": hold.complaint_id,
                "complaint_ref": hold.complaint_ref,
                "bank_id": hold.bank_id,
                "disputed_paise": hold.disputed_paise,
            }
        elif action_in.type is ActionType.OVERRIDE and not (action_in.reason or "").strip():
            raise ValidationFailed("ACTION_REASON_REQUIRED", "an override needs a reason")

        # 4. create the Action
        is_hold = action_in.type is ActionType.REQUEST_HOLD
        action = Action(
            id=new_id(),
            alert_id=alert.id,
            type=action_in.type,
            actor_user_id=principal.user_id,
            actor_role=principal.role.value,
            reason=action_in.reason,
            params=params,
            status=ActionStatus.PENDING if is_hold else ActionStatus.RECORDED,
            at=now,
            status_at=now,
        )
        self._actions.add(action)

        # 5. audit, in the same unit of work as the action itself (LC-9)
        self._audit.append(
            actor_id=principal.user_id,
            actor_role=principal.role.value,
            action="action.recorded",
            entity_type="alert",
            entity_id=alert.id,
            payload={"action_id": action.id, "type": action.type.value, "params": params},
            reason=action_in.reason,
        )

        # 6. transition the alert
        new_status = (
            AlertStatus.ACKNOWLEDGED
            if action_in.type is ActionType.ACKNOWLEDGE
            else AlertStatus.ACTIONED
        )
        alert.transition(
            new_status,
            TimelineEntry(
                id=new_id(),
                alert_id=alert.id,
                at=now,
                kind=new_status.value,
                actor_id=principal.user_id,
                text_code=f"alert.action.{action_in.type.value}",
                text_params={"by": principal.display_name, "action_id": action.id},
            ),
        )
        self._alerts.save(alert)

        # 7. enqueue the deliveries this action causes
        if hold is not None:
            self._enqueue.enqueue_hold_request(
                action,
                alert_id=alert.id,
                bank_id=hold.bank_id,
                account_ref=hold.account_ref,
                complaint_ref=hold.complaint_ref,
                disputed_paise=hold.disputed_paise,
                proposed_paise=hold.proposed_paise,
                expires_at_sim=hold.expires_at,
                review_at_sim=hold.review_at,
                sim_time=now,
            )

        logger.info(
            "alerting.action_recorded",
            alert_id=alert.id,
            action_id=action.id,
            type=action.type.value,
            by=principal.user_id,
        )
        return action

    # ------------------------------------------------------------------

    def _validate_hold(self, params: dict, now: SimTime) -> _HoldRequest:
        """Rebuild the LienProposal through interception.validate_lien; never trust the caller's
        numbers, and never skip the re-validation (DOC 4 A8 drift warning)."""
        account_id = params.get("account_id")
        proposed = params.get("proposed_paise")
        if not isinstance(account_id, str) or not account_id:
            raise ValidationFailed("LIEN_INVALID", "request_hold needs params.account_id")
        if isinstance(proposed, bool) or not isinstance(proposed, int):
            raise ValidationFailed(
                "LIEN_INVALID", "request_hold needs integer params.proposed_paise"
            )
        if self._lien_context is None or self._validate_lien is None:
            raise ValidationFailed("LIEN_INVALID", "hold validation is not wired in this process")

        ctx = self._lien_context.for_account(account_id)
        if ctx is None:
            raise ValidationFailed("LIEN_INVALID", f"{account_id} is not traced from any complaint")

        lien = self._validate_lien(
            complaint_id=ctx.complaint_id,
            account_id=account_id,
            traced_accounts=ctx.traced_accounts,
            disputed_paise=ctx.disputed_paise,
            proposed_paise=proposed,
            active_lien_proposed_total=self._actions.active_hold_total_for_complaint(
                ctx.complaint_id
            ),
            now=now,
        )
        return _HoldRequest(
            account_id=account_id,
            account_ref=ctx.account_ref,
            bank_id=ctx.bank_id,
            complaint_id=ctx.complaint_id,
            complaint_ref=ctx.complaint_ref,
            disputed_paise=lien.disputed_paise,
            proposed_paise=lien.proposed_paise,
            expires_at=lien.expires_at,
            review_at=lien.review_at,
        )


@dataclass(frozen=True, slots=True)
class _HoldRequest:
    account_id: str
    account_ref: str
    bank_id: str
    complaint_id: str
    complaint_ref: str
    disputed_paise: int
    proposed_paise: int
    expires_at: SimTime
    review_at: SimTime
