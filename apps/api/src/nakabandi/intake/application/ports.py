"""Repository ports for intake (DOC 3 LC-9). Every read used for forecasting takes a required
`as_of` (LC-2 as-of rule) and returns only records with `observed_at <= as_of`."""

from __future__ import annotations

from typing import Protocol

from nakabandi.intake.domain.entities import (
    Account,
    CashOutObservation,
    Complaint,
    FundHop,
    IngestBatchRecord,
)
from nakabandi.shared import Id, SimTime


class AccountRepo(Protocol):
    def get_or_create(
        self, *, account_ref: str, bank_id: Id, home_location_id: Id | None, observed_at: SimTime
    ) -> Account: ...
    def get_by_ref(self, account_ref: str) -> Account | None: ...


class ComplaintRepo(Protocol):
    def add(self, complaint: Complaint) -> None: ...
    def get_by_external_ref(self, external_ref: str) -> Complaint | None: ...
    def list_visible(self, as_of: SimTime) -> list[Complaint]: ...


class HopRepo(Protocol):
    def add(self, hop: FundHop) -> None: ...


class ObservationRepo(Protocol):
    def add(self, observation: CashOutObservation) -> None: ...


class BatchRepo(Protocol):
    def get_by_idempotency_key(self, key: str) -> IngestBatchRecord | None: ...
    def record(self, batch: IngestBatchRecord) -> None: ...
