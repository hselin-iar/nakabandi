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

    def list_queue(self, district_id: str | None, start: Any, end: Any) -> list[Any]: ...

    def list_awaiting_outcome(self, target_id: str | None = None) -> list[Any]: ...

    def list_for_review(
        self,
        *,
        state_id: str | None = None,
        district_id: str | None = None,
        bank_id: str | None = None,
        limit: int = 1000,
    ) -> list[Any]: ...

    def list_by_scope(
        self,
        *,
        state_id: str | None = None,
        district_id: str | None = None,
        bank_id: str | None = None,
        status: str | None = None,
        view: str = "all",
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Any], str | None]:
        """Paginated listing filtered by principal scope. Returns (items, next_cursor)."""
        ...

    def save(self, alert: Any) -> None: ...


class OutcomeRepo(Protocol):
    """Read/write access to the outcomes table."""

    def save(self, outcome: Any) -> None: ...
    def list_for_alert(self, alert_id: Id) -> list[Any]: ...
    def find_officer(self, alert_id: Id, result: str, location_id: Id | None) -> Any | None: ...


@dataclass(frozen=True, slots=True)
class ObservedCashOut:
    """An ingested cash-out, as ReconcileOutcome needs it."""

    id: Id
    location_id: Id
    event_at: Any  # SimTime


class ObservationSource(Protocol):
    """Where ReconcileOutcome looks up what an ObservationIngested event (IDs only, LC-3) refers
    to. Implemented over intake in main.py's wiring."""

    def observations(self, observation_ids: list[Id]) -> list[ObservedCashOut]: ...


class ConfirmedCashOutPort(Protocol):
    """graph.apply_confirmed (DOC 3 S3): an officer-confirmed cash-out location becomes an
    observation with source="police_report" at `at`, so the cluster's affinity updates at once."""

    def apply_confirmed(self, cluster_id: Id, location_id: Id, at: Any) -> bool:
        """True if the graph accepted it; False if this process cannot apply it (yet)."""
        ...


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

    def complaint_summary(self, complaint_id: Id) -> Any | None:
        """Category and amount_paise of a complaint (an intake ComplaintSummary), or None."""
        ...

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


class AlertDetailSource(Protocol):
    """Where AlertDetail's `forecast` and `interception` (LC-4) come from: other modules' data,
    read by main.py's wiring through their facades (alerting may not read their tables, LC-10)."""

    def forecast(self, forecast_id: Id) -> Any | None:
        """The forecast an alert last merged (an LC-4 Forecast), or None."""
        ...

    def assessments(self, forecast_id: Id) -> list[Any]:
        """The interception assessments made for that forecast (LC-4 InterceptAssessment)."""
        ...
