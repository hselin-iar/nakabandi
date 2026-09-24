"""SQLAlchemy ORM model for casework's own `cases` table (DOC 3 LC-10)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from nakabandi.shared import Base, UTCDateTime


class CaseModel(Base):
    __tablename__ = "cases"
    __table_args__ = (UniqueConstraint("cluster_ref", name="uq_cases_cluster_ref"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    cluster_ref: Mapped[str] = mapped_column(String, nullable=False, index=True)
    complaint_count: Mapped[int] = mapped_column(Integer, nullable=False)
    victim_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    first_seen: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    last_seen: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    accounts_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    top_locations_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    sub_communities_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    timeline_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    brief_md: Mapped[str] = mapped_column(String, nullable=False, default="")
    single_complaint: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    built_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
