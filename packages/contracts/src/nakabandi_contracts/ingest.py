"""Canonical ingestion contract (LC-1, normative). Pydantic v2 models only, no logic.

This package imports nothing from `nakabandi` (apps/api): it is the leaf of the dependency
graph (DOC 2 §2.6). SimTime here is defined locally rather than imported from
`nakabandi.shared.types` for that reason; both definitions implement the same LC-2 rule
(timezone-aware UTC, naive datetimes rejected).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from nakabandi_contracts.enums import Channel, ComplaintCategory, LocationKind


def _reject_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("naive datetime is not allowed; SimTime must be timezone-aware (LC-2)")
    return value


SimTime = Annotated[datetime, AfterValidator(_reject_naive)]
Id = str
Paise = Annotated[int, Field(gt=0)]


class _Strict(BaseModel):
    """Base for every LC-1 model: unknown fields are rejected, never silently dropped."""

    model_config = ConfigDict(extra="forbid")


class AccountIn(_Strict):
    account_ref: str
    bank_id: Id
    home_location_id: Id | None = None


class ComplaintIn(_Strict):
    external_ref: str
    category: ComplaintCategory
    amount_paise: Paise
    victim_district_id: Id
    credited_at: SimTime
    reported_event_at: SimTime
    observed_at: SimTime
    layer1_account: AccountIn

    @model_validator(mode="after")
    def _check_time_order(self) -> ComplaintIn:
        if not (self.credited_at <= self.reported_event_at <= self.observed_at):
            raise ValueError(
                "credited_at <= reported_event_at <= observed_at must hold (LC-1 rule)"
            )
        return self


class ComplaintBatch(_Strict):
    batch_id: str
    idempotency_key: str
    sim_time: SimTime
    items: list[ComplaintIn] = Field(max_length=500)


class HopIn(_Strict):
    complaint_external_ref: str
    from_account: AccountIn
    to_account: AccountIn
    amount_paise: Paise
    layer: int = Field(ge=1, le=12)
    event_at: SimTime
    observed_at: SimTime

    @model_validator(mode="after")
    def _check_time_order(self) -> HopIn:
        if self.observed_at < self.event_at:
            raise ValueError("observed_at >= event_at must hold (LC-1 rule)")
        return self


class HopBatch(_Strict):
    batch_id: str
    idempotency_key: str
    sim_time: SimTime
    items: list[HopIn] = Field(max_length=500)


class CashOutObsIn(_Strict):
    account_ref: str
    location_id: Id
    channel: Channel
    amount_paise: Paise
    event_at: SimTime
    observed_at: SimTime
    source: Literal["bank_report", "police_report"]

    @model_validator(mode="after")
    def _check_time_order(self) -> CashOutObsIn:
        if self.observed_at < self.event_at:
            raise ValueError("observed_at >= event_at must hold (LC-1 rule)")
        return self


class CashOutObservationBatch(_Strict):
    batch_id: str
    idempotency_key: str
    sim_time: SimTime
    items: list[CashOutObsIn] = Field(max_length=500)


class RegistryLocation(_Strict):
    id: Id
    kind: LocationKind
    bank_id: Id
    lat: float
    lon: float
    district_id: Id
    cell_id: Id
    source: Literal["osm", "synthetic"]
    display_name: str
    area_type: Literal["urban", "semi_urban", "rural"]
    activity_index: float = Field(ge=0, le=1)


class RegistryUnit(_Strict):
    id: Id
    kind: Literal["cyber_cell", "station", "patrol"]
    district_id: Id
    lat: float
    lon: float
    status: str


class RegistryUpdate(_Strict):
    version: str
    # banks/regions/cells item shapes are not spelled out in LC-1 beyond the field name;
    # kept as opaque objects here rather than inventing a shape (AP-09). Track A refines
    # these when geo/intake first consume them (Step A3).
    banks: list[dict[str, Any]]
    regions: list[dict[str, Any]]
    cells: list[dict[str, Any]]
    locations: list[RegistryLocation]
    units: list[RegistryUnit]


class Tick(_Strict):
    sim_time: SimTime


class RejectedItem(_Strict):
    index: int
    code: str
    message: str


class IngestResponse(_Strict):
    """The `Response (all)` shape in LC-1: shared by every ingestion endpoint."""

    accepted: int
    rejected: list[RejectedItem]
    sim_time: SimTime
