"""models.py — SQLAlchemy ORM model for the `evidence_packs` table (DOC 3 S2, LC-10: casework
owns this table)."""

from __future__ import annotations

from datetime import datetime

from nakabandi.shared import Base, UTCDateTime
from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column


class EvidencePackModel(Base):
    __tablename__ = "evidence_packs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    alert_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    case_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    created_by_role: Mapped[str] = mapped_column(String, nullable=False)
    sha256: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    audit_head_hash: Mapped[str] = mapped_column(String, nullable=False)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
