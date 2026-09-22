"""ApplyRegistry: idempotent upsert of a registry snapshot (DOC 3 M3 "ApplyRegistry (from
IngestRegistry)"; DOC 2 §2.4 "banks, locations, units, regions (idempotent upsert)").

Called by intake.IngestRegistry through the geo facade (intake may not touch geo's tables
directly, LC-10). Processes banks, then regions, then cells, then locations, then units, so a
location or unit in the same snapshot can reference a bank/region/cell also being applied.
Each row is independent: one bad row is reported in `rejected` and never stops the rest
(DOC 3 M2 "Validation errors reject the whole ingest batch item with a per-item error list").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nakabandi_contracts.ingest import RegistryLocation, RegistryUnit

from nakabandi.geo.application.ports import BankRepo, CellRepo, LocationRepo, RegionRepo, UnitRepo
from nakabandi.geo.domain.entities import Location, Unit
from nakabandi.geo.domain.parsing import parse_bank, parse_cell, parse_region
from nakabandi.shared import DomainError


@dataclass(slots=True)
class RejectedRow:
    index: int
    code: str
    message: str


@dataclass(slots=True)
class ApplyRegistryResult:
    accepted: int
    rejected: list[RejectedRow] = field(default_factory=list)


class ApplyRegistry:
    def __init__(
        self,
        bank_repo: BankRepo,
        region_repo: RegionRepo,
        cell_repo: CellRepo,
        location_repo: LocationRepo,
        unit_repo: UnitRepo,
    ) -> None:
        self._banks = bank_repo
        self._regions = region_repo
        self._cells = cell_repo
        self._locations = location_repo
        self._units = unit_repo

    def run(
        self,
        *,
        banks: list[dict[str, Any]],
        regions: list[dict[str, Any]],
        cells: list[dict[str, Any]],
        locations: list[RegistryLocation],
        units: list[RegistryUnit],
    ) -> ApplyRegistryResult:
        accepted = 0
        rejected: list[RejectedRow] = []
        index = 0

        for raw in banks:
            try:
                self._banks.upsert(parse_bank(raw, index))
                accepted += 1
            except DomainError as exc:
                rejected.append(RejectedRow(index, exc.code, exc.message))
            index += 1

        for raw in regions:
            try:
                self._regions.upsert(parse_region(raw, index))
                accepted += 1
            except DomainError as exc:
                rejected.append(RejectedRow(index, exc.code, exc.message))
            index += 1

        for raw in cells:
            try:
                self._cells.upsert(parse_cell(raw, index))
                accepted += 1
            except DomainError as exc:
                rejected.append(RejectedRow(index, exc.code, exc.message))
            index += 1

        for loc in locations:
            try:
                self._locations.upsert(
                    Location(
                        id=loc.id,
                        kind=loc.kind.value,
                        bank_id=loc.bank_id,
                        lat=loc.lat,
                        lon=loc.lon,
                        district_id=loc.district_id,
                        cell_id=loc.cell_id,
                        source=loc.source,
                        display_name=loc.display_name,
                        area_type=loc.area_type,
                        activity_index=loc.activity_index,
                    )
                )
                accepted += 1
            except DomainError as exc:
                rejected.append(RejectedRow(index, exc.code, exc.message))
            index += 1

        for unit in units:
            try:
                self._units.upsert(
                    Unit(
                        id=unit.id,
                        kind=unit.kind,
                        district_id=unit.district_id,
                        lat=unit.lat,
                        lon=unit.lon,
                        status=unit.status,
                        speed_profile=None,
                    )
                )
                accepted += 1
            except DomainError as exc:
                rejected.append(RejectedRow(index, exc.code, exc.message))
            index += 1

        return ApplyRegistryResult(accepted=accepted, rejected=rejected)
