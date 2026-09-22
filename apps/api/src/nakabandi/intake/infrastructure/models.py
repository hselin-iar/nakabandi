"""SQLAlchemy ORM models for intake's tables (DOC 3 LC-10: intake owns accounts, complaints,
fund_hops, cashout_observations, ingest_batches)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from nakabandi.shared import Base


class AccountModel(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("account_ref", name="uq_accounts_account_ref"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    account_ref: Mapped[str] = mapped_column(String, nullable=False, index=True)
    bank_id: Mapped[str] = mapped_column(String, nullable=False)
    home_location_id: Mapped[str | None] = mapped_column(String, nullable=True)
    home_district_id: Mapped[str | None] = mapped_column(String, nullable=True)
    first_seen_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ComplaintModel(Base):
    __tablename__ = "complaints"
    __table_args__ = (UniqueConstraint("external_ref", name="uq_complaints_external_ref"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    external_ref: Mapped[str] = mapped_column(String, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    victim_district_id: Mapped[str] = mapped_column(String, nullable=False)
    credited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reported_event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    layer1_account_id: Mapped[str] = mapped_column(
        String, ForeignKey("accounts.id"), nullable=False, index=True
    )
    processing_status: Mapped[str] = mapped_column(String, nullable=False, default="unprocessed")


class FundHopModel(Base):
    __tablename__ = "fund_hops"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    complaint_id: Mapped[str] = mapped_column(
        String, ForeignKey("complaints.id"), nullable=False, index=True
    )
    from_account_id: Mapped[str] = mapped_column(
        String, ForeignKey("accounts.id"), nullable=False, index=True
    )
    to_account_id: Mapped[str] = mapped_column(
        String, ForeignKey("accounts.id"), nullable=False, index=True
    )
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    layer: Mapped[int] = mapped_column(Integer, nullable=False)
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CashOutObservationModel(Base):
    __tablename__ = "cashout_observations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String, ForeignKey("accounts.id"), nullable=False, index=True
    )
    location_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String, nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String, nullable=False)


class IngestBatchModel(Base):
    __tablename__ = "ingest_batches"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ingest_batches_idempotency_key"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    row_counts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
