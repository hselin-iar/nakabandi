"""SQLAlchemy ORM model for audit's table (DOC 3 LC-10: audit owns audit_entries)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from nakabandi.shared import Base, UTCDateTime


class AuditEntryModel(Base):
    __tablename__ = "audit_entries"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    actor_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    actor_role: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    prev_hash: Mapped[str] = mapped_column(String, nullable=False)
    hash: Mapped[str] = mapped_column(String, nullable=False)
