"""Answers "which state, district and bank does this location belong to?" for alerting, which
copies the answer onto each alert so it can be filtered by a principal's scope (DOC 3 M5
authorize, DOC 2 §2.3 Alert.scope_*). Alerting may not read geo's tables (LC-10)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from nakabandi.geo.infrastructure.models import LocationModel, RegionModel


@dataclass(frozen=True, slots=True)
class LocationScope:
    state_id: str | None
    district_id: str
    bank_id: str
    cell_id: str | None = None
    kind: str | None = None  # ATM | BRANCH | AGENT
    name: str | None = None


class LocationScopeLookup:
    def __init__(self, session: Session) -> None:
        self._session = session

    def for_location(self, location_id: str) -> LocationScope | None:
        location = self._session.get(LocationModel, location_id)
        if location is None:
            return None
        district = self._session.get(RegionModel, location.district_id)
        return LocationScope(
            state_id=district.parent_id if district is not None else None,
            district_id=location.district_id,
            bank_id=location.bank_id,
            cell_id=location.cell_id,
            kind=location.kind,
            name=location.display_name,
        )
