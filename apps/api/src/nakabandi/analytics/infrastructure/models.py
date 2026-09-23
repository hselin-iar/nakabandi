"""heat_rollups (LC-10: analytics owns it; DOC 2 §2.3 HeatRollup)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from nakabandi.shared import Base, UTCDateTime


class HeatRollupModel(Base):
    __tablename__ = "heat_rollups"
    __table_args__ = (
        Index("ix_heat_rollups_hour_category", "hour_bucket", "category"),
        Index("ix_heat_rollups_layer_hour", "layer", "hour_bucket"),
    )

    # The DOC 2 key: (target_kind, target_id, hour_bucket, category, amount_band,
    # confidence_band, layer).
    target_kind: Mapped[str] = mapped_column(String, primary_key=True)
    target_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    hour_bucket: Mapped[datetime] = mapped_column(UTCDateTime, primary_key=True)
    category: Mapped[str] = mapped_column(String, primary_key=True)
    amount_band: Mapped[int] = mapped_column(Integer, primary_key=True)
    confidence_band: Mapped[int] = mapped_column(Integer, primary_key=True)
    layer: Mapped[str] = mapped_column(String, primary_key=True)
    expected_mass: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    alert_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
