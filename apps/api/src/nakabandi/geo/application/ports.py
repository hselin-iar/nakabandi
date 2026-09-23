"""Repository ports for geo (DOC 3 LC-9: repositories are Protocols; infrastructure implements
them). Registry ingestion is an idempotent upsert (DOC 2 §2.4: "banks, locations, units, regions
(idempotent upsert)"), so every port exposes only `upsert`."""

from __future__ import annotations

from typing import Protocol

from nakabandi.geo.domain.entities import Bank, Cell, Location, Region, Unit


class BankRepo(Protocol):
    def upsert(self, bank: Bank) -> None: ...


class RegionRepo(Protocol):
    def upsert(self, region: Region) -> None: ...


class CellRepo(Protocol):
    def upsert(self, cell: Cell) -> None: ...


class LocationRepo(Protocol):
    def upsert(self, location: Location) -> None: ...
    def exists(self, location_id: str) -> bool: ...


class UnitRepo(Protocol):
    def upsert(self, unit: Unit) -> None: ...
