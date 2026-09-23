"""SQLAlchemy ORM models for geo's tables (DOC 3 LC-10: geo owns regions, banks, locations,
cells, units). `region.parent_id` is a plain string, not an enforced foreign key: a
RegistryUpdate's `regions` array carries no order guarantee between a parent and its child, so
a self-referential FK could reject a well-formed batch depending on array order.
"""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from nakabandi.shared import Base


class RegionModel(Base):
    __tablename__ = "regions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    level: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    geojson_ref: Mapped[str | None] = mapped_column(String, nullable=True)


class BankModel(Base):
    __tablename__ = "banks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    short_code: Mapped[str] = mapped_column(String, nullable=False)


class CellModel(Base):
    __tablename__ = "cells"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    grid_km: Mapped[float] = mapped_column(Float, nullable=False)
    row: Mapped[int] = mapped_column(Integer, nullable=False)
    col: Mapped[int] = mapped_column(Integer, nullable=False)
    district_id: Mapped[str] = mapped_column(
        String, ForeignKey("regions.id"), nullable=False, index=True
    )
    centroid_lat: Mapped[float] = mapped_column(Float, nullable=False)
    centroid_lon: Mapped[float] = mapped_column(Float, nullable=False)


class LocationModel(Base):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    bank_id: Mapped[str] = mapped_column(String, ForeignKey("banks.id"), nullable=False, index=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    district_id: Mapped[str] = mapped_column(
        String, ForeignKey("regions.id"), nullable=False, index=True
    )
    cell_id: Mapped[str] = mapped_column(String, ForeignKey("cells.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    area_type: Mapped[str] = mapped_column(String, nullable=False)
    activity_index: Mapped[float] = mapped_column(Float, nullable=False)


class UnitModel(Base):
    __tablename__ = "units"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    district_id: Mapped[str] = mapped_column(
        String, ForeignKey("regions.id"), nullable=False, index=True
    )
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    speed_profile: Mapped[str | None] = mapped_column(String, nullable=True)
