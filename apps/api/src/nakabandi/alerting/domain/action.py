"""Action entity and its status lifecycle (DOC 3 M4, DOC 2 §2.3 Action).

An Action is what a human decided to do about an alert. It is created only by RecordAction
(the human gate, DOC 2 §2.1 invariant 7). For `request_hold` the status then follows the bank's
callbacks (LC-6): pending -> applied | rejected, applied -> released. Every other action type is
`recorded` at once because nothing outside our own system has to confirm it.
"""

from __future__ import annotations

from collections.abc import Set
from dataclasses import dataclass
from enum import StrEnum

from nakabandi_contracts.enums import ActionType, Permission

from nakabandi.shared import Id, SimTime


class ActionStatus(StrEnum):
    PENDING = "pending"  # request_hold sent, waiting for the bank
    RECORDED = "recorded"  # internal action, nothing to wait for
    APPLIED = "applied"  # bank callback statuses (LC-6)
    REJECTED = "rejected"
    RELEASED = "released"


_PROGRESS = {
    ActionStatus.PENDING: 0,
    ActionStatus.RECORDED: 0,
    ActionStatus.APPLIED: 1,
    ActionStatus.REJECTED: 1,
    ActionStatus.RELEASED: 2,
}

_PERMISSION_FOR: dict[ActionType, Permission] = {
    ActionType.ACKNOWLEDGE: Permission.ACKNOWLEDGE,
    ActionType.REQUEST_HOLD: Permission.REQUEST_HOLD,
    ActionType.NOTIFY_STATION: Permission.NOTIFY_STATION,
    ActionType.DISPATCH: Permission.DISPATCH,
    ActionType.OVERRIDE: Permission.OVERRIDE,
}


def permission_for(action_type: ActionType) -> Permission:
    return _PERMISSION_FOR[action_type]


def allowed_actions(permissions: Set[Permission]) -> list[ActionType]:
    """Action types a role holding `permissions` may record (LC-4 allowed_actions)."""
    return [t for t in ActionType if permission_for(t) in permissions]


@dataclass(slots=True)
class Action:
    id: Id  # also the LC-6 `request_id` for a request_hold
    alert_id: Id
    type: ActionType
    actor_user_id: Id
    actor_role: str
    reason: str | None
    params: dict
    status: ActionStatus
    at: SimTime
    status_at: SimTime  # sim time of the latest status; callbacks older than this are ignored
    note: str | None = None
    applied_amount_paise: int | None = None

    def apply_callback(
        self,
        status: ActionStatus,
        at_sim: SimTime,
        applied_amount_paise: int | None,
        note: str | None,
    ) -> bool:
        """Latest status wins (DOC 3 M4 edge case: "Bank callback arrives twice or out of order").

        A callback is newer if its sim time is later than the last one held. At the SAME sim time
        the order is settled by how far the request has progressed (pending, then applied or
        rejected, then released): a forward step is accepted, a duplicate or a step backwards is
        ignored. This matters in practice: the bank's fallback sim time is the latest webhook's, so
        an operator who acts straight away reports the very instant the hold was created, and an
        apply followed at once by a release share one sim time too. Returns False when ignored."""
        newer = at_sim > self.status_at or (
            at_sim == self.status_at and _PROGRESS[status] > _PROGRESS[self.status]
        )
        if not newer:
            return False
        self.status = status
        self.status_at = at_sim
        if applied_amount_paise is not None:
            self.applied_amount_paise = applied_amount_paise
        if note is not None:
            self.note = note
        return True
