"""Public facade of nakabandi.shared: the only code every track imports (DOC 3 Shared Kernel).

Edits follow the Contract Change Process. Additions (a new enum member, a new event) are
announced; removals and renames are not allowed.
"""

from nakabandi.shared.clock import Clock, SimClock, SystemClock
from nakabandi.shared.config import Settings, get_settings
from nakabandi.shared.errors import (
    Conflict,
    DomainError,
    ExternalFailure,
    Forbidden,
    InvariantViolated,
    NotFound,
    Unauthenticated,
    ValidationFailed,
)
from nakabandi.shared.events import (
    ClusterMerged,
    ClusterUpdated,
    DomainEvent,
    EventBus,
    HandlerError,
)
from nakabandi.shared.ids import new_id
from nakabandi.shared.messages import message_for
from nakabandi.shared.policy import Policy, PolicyLoadError
from nakabandi.shared.scheduler import Scheduler
from nakabandi.shared.types import Id, Paise, SimTime, paise_from_inr, to_sim_time
from nakabandi.shared.uow import UnitOfWork

__all__ = [
    "Clock",
    "SimClock",
    "SystemClock",
    "Settings",
    "get_settings",
    "Conflict",
    "DomainError",
    "ExternalFailure",
    "Forbidden",
    "InvariantViolated",
    "NotFound",
    "Unauthenticated",
    "ValidationFailed",
    "DomainEvent",
    "EventBus",
    "HandlerError",
    "ClusterMerged",
    "ClusterUpdated",
    "new_id",
    "message_for",
    "Policy",
    "PolicyLoadError",
    "Scheduler",
    "Id",
    "Paise",
    "SimTime",
    "paise_from_inr",
    "to_sim_time",
    "UnitOfWork",
]
