"""HandleBankCallback (DOC 3 M4, LC-6): the bank tells us what became of a hold request."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import structlog

from nakabandi.alerting.application.ports import ActionRepo, AlertRepo
from nakabandi.alerting.domain.action import Action, ActionStatus
from nakabandi.alerting.domain.alert import TimelineEntry
from nakabandi.audit import AuditLog
from nakabandi.shared import Clock, NotFound, ValidationFailed, new_id, to_sim_time

logger = structlog.get_logger(__name__)

_CALLBACK_STATUSES = {ActionStatus.APPLIED, ActionStatus.REJECTED, ActionStatus.RELEASED}
BANK_ACTOR_ID = "bank-gateway"
BANK_ACTOR_ROLE = "bank_gateway"


@dataclass(frozen=True, slots=True)
class BankCallback:
    """LC-6 callback body: { request_id, status, applied_amount_paise?, at_sim, note? }."""

    request_id: str
    status: str
    at_sim: datetime
    applied_amount_paise: int | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class CallbackResult:
    action: Action
    applied: bool  # False when the callback was a duplicate or older than what we hold


class HandleBankCallback:
    """The service key is checked by the router (a machine client, no Principal)."""

    def __init__(
        self, action_repo: ActionRepo, alert_repo: AlertRepo, audit: AuditLog, clock: Clock
    ) -> None:
        self._actions = action_repo
        self._alerts = alert_repo
        self._audit = audit
        self._clock = clock

    def run(self, cb: BankCallback) -> CallbackResult:
        action: Action | None = self._actions.get_by_id(cb.request_id)
        if action is None:
            raise NotFound("ACTION_NOT_FOUND", f"no action for request_id {cb.request_id!r}")
        try:
            status = ActionStatus(cb.status)
        except ValueError:
            status = ActionStatus.PENDING  # not a callback status; rejected just below
        if status not in _CALLBACK_STATUSES:
            raise ValidationFailed("CALLBACK_INVALID", f"unknown callback status {cb.status!r}")
        if status is ActionStatus.APPLIED:
            proposed = int(action.params.get("proposed_paise", 0))
            amount = cb.applied_amount_paise
            if amount is None or not (0 < amount <= proposed):
                raise ValidationFailed(
                    "CALLBACK_INVALID",
                    f"applied_amount_paise must be in (0, {proposed}], got {amount!r}",
                )

        changed = action.apply_callback(
            status, to_sim_time(cb.at_sim), cb.applied_amount_paise, cb.note
        )
        if not changed:
            logger.info(
                "alerting.bank_callback.ignored",
                request_id=cb.request_id,
                status=cb.status,
                at_sim=cb.at_sim.isoformat(),
            )
            return CallbackResult(action, applied=False)

        self._actions.save(action)
        self._audit.append(
            actor_id=BANK_ACTOR_ID,
            actor_role=BANK_ACTOR_ROLE,
            action="action.bank_callback",
            entity_type="action",
            entity_id=action.id,
            payload={
                "status": status.value,
                "applied_amount_paise": cb.applied_amount_paise,
                "at_sim": cb.at_sim.isoformat(),
            },
            reason=cb.note,
        )
        alert = self._alerts.get_by_id(action.alert_id)
        if alert is not None:
            alert.timeline.append(
                TimelineEntry(
                    id=new_id(),
                    alert_id=alert.id,
                    at=self._clock.now(),
                    kind="bank_callback",
                    actor_id=None,
                    text_code=f"alert.hold.{status.value}",
                    text_params={
                        "action_id": action.id,
                        "applied_amount_paise": cb.applied_amount_paise,
                    },
                )
            )
            self._alerts.save(alert)
        return CallbackResult(action, applied=True)
