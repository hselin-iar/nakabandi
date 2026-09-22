"""Public facade of the geo module: what other modules may import (DOC 3).

GeoService is constructed on the caller's active SQLAlchemy session, so an IngestRegistry batch
and its ApplyRegistry effects share one transaction/UnitOfWork (LC-9). Only `apply_registry` is
built at Step A3; `regions`, `locations`, `cell_of` and `spatial_index` (DOC 3 M3) land at
Step A9 (Analytics Read Model & Heatmap API) alongside the geo query endpoints.
"""

from __future__ import annotations

from typing import Any

from nakabandi_contracts.ingest import RegistryLocation, RegistryUnit
from sqlalchemy.orm import Session

from nakabandi.geo.application.apply_registry import ApplyRegistry, ApplyRegistryResult
from nakabandi.geo.infrastructure.repositories import (
    SqlBankRepo,
    SqlCellRepo,
    SqlLocationRepo,
    SqlRegionRepo,
    SqlUnitRepo,
)

__all__ = ["GeoService", "ApplyRegistryResult"]


class GeoService:
    def __init__(self, session: Session) -> None:
        self._apply_registry = ApplyRegistry(
            bank_repo=SqlBankRepo(session),
            region_repo=SqlRegionRepo(session),
            cell_repo=SqlCellRepo(session),
            location_repo=SqlLocationRepo(session),
            unit_repo=SqlUnitRepo(session),
        )

    def apply_registry(
        self,
        *,
        banks: list[dict[str, Any]],
        regions: list[dict[str, Any]],
        cells: list[dict[str, Any]],
        locations: list[RegistryLocation],
        units: list[RegistryUnit],
    ) -> ApplyRegistryResult:
        return self._apply_registry.run(
            banks=banks, regions=regions, cells=cells, locations=locations, units=units
        )
