"""Alerting application ports (Protocols) (DOC 3 M4 application/ports.py)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from nakabandi.shared import Id


class AlertRepo(Protocol):
    """Read/write access to the alerts table (LC-10 alerting owns alerts)."""

    def get_by_id(self, alert_id: Id) -> Any | None: ...

    def get_by_dedup_key(self, dedup_key: str) -> Any | None:
        """Return the open alert with this dedup_key, or None."""
        ...

    def list_open(self) -> list[Any]: ...

    def list_by_scope(
        self,
        *,
        state_id: str | None = None,
        district_id: str | None = None,
        bank_id: str | None = None,
        status: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Any], str | None]:
        """Paginated listing filtered by principal scope. Returns (items, next_cursor)."""
        ...

    def save(self, alert: Any) -> None: ...


class OutcomeRepo(Protocol):
    """Read/write access to the outcomes table."""

    def save(self, outcome: Any) -> None: ...


class DirectoryPort(Protocol):
    """Stub port for the geo directory (real implementation lands at Sync 4)."""

    def get_recipients(self, alert: Any) -> list[Any]: ...


class ActionRepo(Protocol):
    def get_by_id(self, action_id: Id) -> Any | None: ...
    def list_for_alert(self, alert_id: Id) -> list[Any]: ...
    def active_hold_total_for_complaint(self, complaint_id: Id) -> int: ...
    def list_active_holds(self) -> list[Any]: ...
    def add(self, action: Any) -> None: ...
    def save(self, action: Any) -> None: ...


class DeliveryRepo(Protocol):
    def add(self, delivery: Any) -> None: ...
    def save(self, delivery: Any) -> None: ...
    def get_by_id(self, delivery_id: Id) -> Any | None: ...
    def list_due(self, now_wall: Any, limit: int = 50) -> list[Any]: ...
    def list_for_alert(self, alert_id: Id) -> list[Any]: ...


class NotificationChannel(Protocol):
    """Adapters only send (DOC 3 M4): a failure comes back as a DeliveryResult, never as a raised
    error, and the outbox turns it into a Delivery row update."""

    def send(self, delivery: Any) -> Any:  # -> DeliveryResult
        ...


@dataclass(frozen=True, slots=True)
class LienContext:
    """Everything RecordAction needs to re-validate a hold request, none of which alerting owns
    (LC-10): the traced accounts and the disputed amount come from intake (see LienContextPort)."""

    complaint_id: Id
    complaint_ref: str
    account_ref: str
    bank_id: str
    traced_accounts: list[Id]
    disputed_paise: int


class LienContextPort(Protocol):
    """Answers, from intake, questions about the complaint an alert is anchored to."""

    def for_account(self, complaint_id: Id, account_id: Id) -> Any | None:
        """The trace of one account within one complaint (an intake AccountTrace), or None if
        that complaint's money never reached the account."""
        ...

    def complaint_ref(self, complaint_id: Id) -> str | None: ...

    def traced_accounts(self, complaint_id: Id) -> list[Any]:
        """Every account the complaint reached: objects with bank_id and account_ref."""
        ...


class TargetScopePort(Protocol):
    def for_location(self, location_id: Id) -> Any | None:
        """The state/district/bank a location belongs to (a geo LocationScope), or None."""
        ...


class LienValidator(Protocol):
    """interception.validate_lien; raises LienInvalid (a ValidationFailed) on any violation."""

    def __call__(
        self,
        complaint_id: Id,
        account_id: Id,
        traced_accounts: list[Id],
        disputed_paise: int,
        proposed_paise: int,
        active_lien_proposed_total: int,
        now: Any,
    ) -> Any: ...


class TemplateRenderer(Protocol):
    def render(self, kind: str, locale: str, **params: str) -> str: ...
