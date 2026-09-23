"""Intake domain entities (DOC 2 §2.3 CORE ENTITIES, intake section; DOC 3 LC-10 table
ownership). Plain dataclasses: no SQLAlchemy, no pydantic."""

from __future__ import annotations

from dataclasses import dataclass, field

from nakabandi.shared import Id, Paise, SimTime


@dataclass(slots=True)
class Account:
    id: Id
    account_ref: str
    bank_id: Id
    home_location_id: Id | None
    home_district_id: Id | None
    first_seen_observed_at: SimTime


@dataclass(slots=True)
class Complaint:
    id: Id
    external_ref: str
    category: str
    amount_paise: Paise
    victim_district_id: Id
    credited_at: SimTime
    reported_event_at: SimTime
    observed_at: SimTime
    layer1_account_id: Id
    processing_status: str = "unprocessed"  # processed | unprocessed
    failed_stage: str | None = None  # set by pipeline when processing_status is 'unprocessed'


@dataclass(slots=True)
class FundHop:
    id: Id
    complaint_id: Id
    from_account_id: Id
    to_account_id: Id
    amount_paise: Paise
    layer: int
    event_at: SimTime
    observed_at: SimTime


@dataclass(slots=True)
class CashOutObservation:
    id: Id
    account_id: Id
    location_id: Id
    channel: str
    amount_paise: Paise
    event_at: SimTime
    observed_at: SimTime
    source: str  # bank_report | police_report


@dataclass(slots=True)
class IngestBatchRecord:
    id: Id
    idempotency_key: str
    source: str
    received_at: SimTime
    row_counts: dict[str, int] = field(default_factory=dict)
    response: dict | None = None
    """The cached IngestResponse body (accepted, rejected, sim_time), replayed verbatim when the
    same idempotency_key is posted again (DOC 3 A3 Done When: "resending ... is a no-op")."""
