"""SQLAlchemy ORM models for alerting's tables (LC-10: alerting owns alerts, outcomes).

alert_timeline is an implementation detail of alerts (not in LC-10 explicitly, but owned
by alerting as the alerting.Alert entity's history).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from nakabandi.shared import Base, UTCDateTime


class AlertModel(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        # Partial unique index on open dedup keys (DOC 3 M4 performance note)
        # SQLite doesn't support partial indexes via DDL in SA easily; we use a
        # non-partial unique index on dedup_key + status pair instead.  A trigger or
        # application-level check guards the invariant that only one OPEN alert exists
        # per dedup_key (enforced in SqlAlertRepo.get_by_dedup_key).
        Index("ix_alerts_status_severity", "status", "severity"),
        Index("ix_alerts_dedup_key", "dedup_key"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    cluster_ref: Mapped[str] = mapped_column(String, nullable=False, index=True)
    target_kind: Mapped[str] = mapped_column(String, nullable=False)
    target_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    target_name: Mapped[str] = mapped_column(String, nullable=False)
    dedup_key: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    ladder_level: Mapped[str] = mapped_column(String, nullable=False)
    is_deferred: Mapped[bool] = mapped_column(nullable=False, default=False)
    is_probe: Mapped[bool] = mapped_column(nullable=False, default=False)
    window_start: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    window_end: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    forecast_id: Mapped[str] = mapped_column(String, nullable=False)
    complaint_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    masked: Mapped[bool] = mapped_column(nullable=False, default=False)
    scope_state_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    scope_district_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    scope_bank_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    priority: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    budget_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AlertTimelineModel(Base):
    __tablename__ = "alert_timeline"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    alert_id: Mapped[str] = mapped_column(
        String, ForeignKey("alerts.id"), nullable=False, index=True
    )
    at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    text_code: Mapped[str] = mapped_column(String, nullable=False)
    text_params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class OutcomeModel(Base):
    __tablename__ = "outcomes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    alert_id: Mapped[str] = mapped_column(
        String, ForeignKey("alerts.id"), nullable=False, index=True
    )
    result: Mapped[str] = mapped_column(String, nullable=False)
    observation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False, default="reconciled", index=True)
    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    location_id: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)


class ActionModel(Base):
    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    alert_id: Mapped[str] = mapped_column(
        String, ForeignKey("alerts.id"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
    actor_user_id: Mapped[str] = mapped_column(String, nullable=False)
    actor_role: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String, nullable=False)
    at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    status_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    applied_amount_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)


class DeliveryModel(Base):
    __tablename__ = "deliveries"
    __table_args__ = (
        # The outbox index (DOC 2 §2.3): the worker scans (status, next_attempt_at).
        Index("ix_deliveries_outbox", "status", "next_attempt_at"),
        # "A hold_request delivery cannot exist without an Action row" (DOC 3 M4), enforced by
        # the database as well as by the Delivery entity.
        CheckConstraint(
            "webhook_kind IS NULL OR webhook_kind != 'hold_request' OR action_id IS NOT NULL",
            name="ck_deliveries_hold_request_has_action",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    alert_id: Mapped[str] = mapped_column(
        String, ForeignKey("alerts.id"), nullable=False, index=True
    )
    action_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("actions.id"), nullable=True, index=True
    )
    channel: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    webhook_kind: Mapped[str | None] = mapped_column(String, nullable=True)
    recipient: Mapped[str] = mapped_column(String, nullable=False)
    rendered_body: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
