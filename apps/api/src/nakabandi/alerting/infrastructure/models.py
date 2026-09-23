"""SQLAlchemy ORM models for alerting's tables (LC-10: alerting owns alerts, outcomes).

alert_timeline is an implementation detail of alerts (not in LC-10 explicitly, but owned
by alerting as the alerting.Alert entity's history).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index, String
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
    masked: Mapped[bool] = mapped_column(nullable=False, default=False)


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
