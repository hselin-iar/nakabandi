"""Adapters that let one module read another through its facade, wired in main.py (DOC 2 §2.6:
only `pipeline` and `main.py` see several modules at once). Each is built per request on that
request's session, so a projector reads what the publisher just wrote."""

from __future__ import annotations

from datetime import UTC

import structlog
from sqlalchemy.orm import Session

from nakabandi.alerting import ObservedCashOut
from nakabandi.alerting.infrastructure.repos import SqlAlertRepo
from nakabandi.analytics import (
    AlertFacts,
    CatalogCell,
    CatalogLocation,
    ComplaintFacts,
    ForecastFacts,
    GeoCatalog,
)
from nakabandi.forecast.infrastructure.repositories import SqlForecastRepo
from nakabandi.geo import GeoService
from nakabandi.intake import LienContextLookup

logger = structlog.get_logger(__name__)


class ProjectionSourceAdapter:
    """analytics.ProjectionSource over alerting, forecast and intake."""

    def __init__(self, session: Session) -> None:
        self._alerts = SqlAlertRepo(session)
        self._forecasts = SqlForecastRepo(session)
        self._complaints = LienContextLookup(session)

    def alert_facts(self, alert_id: str) -> AlertFacts | None:
        alert = self._alerts.get_by_id(alert_id)
        if alert is None:
            return None
        return AlertFacts(
            alert_id=alert.id,
            complaint_id=alert.complaint_id,
            target_id=alert.target_id,
            created_at=alert.created_at,
        )

    def forecast_facts(self, complaint_id: str) -> ForecastFacts | None:
        forecast = self._forecasts.get_latest(complaint_id)
        if forecast is None:
            return None

        def items(resolution: str) -> list[tuple[str, float]]:
            level = forecast.levels.get(resolution)
            if level is None or level.abstained:
                return []
            return [(i.id, i.prob) for i in level.items]

        # forecast's table uses a plain DateTime column, which SQLite hands back naive (the A4
        # gotcha; shared.UTCDateTime is the fix). Values are stored as UTC, so re-attach it.
        generated_at = forecast.generated_at
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=UTC)

        return ForecastFacts(
            forecast_id=forecast.id,
            complaint_id=forecast.complaint_id,
            generated_at=generated_at,
            confidence=forecast.confidence,
            p120=forecast.timing.p120,
            cell_items=items("cell"),
            location_items=items("location"),
        )

    def complaint_facts(self, complaint_id: str) -> ComplaintFacts | None:
        summary = self._complaints.complaint_summary(complaint_id)
        if summary is None:
            return None
        return ComplaintFacts(category=summary.category, amount_paise=summary.amount_paise)


class GeoCatalogAdapter:
    """analytics.GeoCatalogPort over the geo facade."""

    def __init__(self, session: Session) -> None:
        self._geo = GeoService(session)

    def catalog(self) -> GeoCatalog:
        regions = {r.id: r for r in self._geo.regions()}

        def state_of(district_id: str) -> str | None:
            district = regions.get(district_id)
            return district.parent_id if district is not None else None

        return GeoCatalog(
            cells={
                c.id: CatalogCell(
                    id=c.id,
                    district_id=c.district_id,
                    state_id=state_of(c.district_id),
                    lat=c.centroid_lat,
                    lon=c.centroid_lon,
                )
                for c in self._geo.cells()
            },
            locations={
                loc.id: CatalogLocation(
                    id=loc.id,
                    name=loc.display_name,
                    cell_id=loc.cell_id,
                    district_id=loc.district_id,
                    state_id=state_of(loc.district_id),
                    bank_id=loc.bank_id,
                    lat=loc.lat,
                    lon=loc.lon,
                )
                for loc in self._geo.locations(limit=1_000_000)
            },
            district_names={r.id: r.name for r in regions.values() if r.level == "district"},
        )


class ObservationSourceAdapter:
    """alerting.ObservationSource over intake: what an ObservationIngested event's IDs refer to."""

    def __init__(self, session: Session) -> None:
        self._intake = LienContextLookup(session)

    def observations(self, observation_ids: list[str]) -> list[ObservedCashOut]:
        return [
            ObservedCashOut(id=o.id, location_id=o.location_id, event_at=o.event_at)
            for o in self._intake.observation_summaries(observation_ids)
        ]


class ConfirmedCashOutPending:
    """alerting.ConfirmedCashOutPort until Track B's graph ships `apply_confirmed` (DOC 4 A10
    STUB/MOCK STRATEGY: "stub it with a recording fake and swap at the next merge").

    It is deliberately NOT silent: it says so in the log and reports False, and MarkOutcome logs
    that the confirmation reached the outcome row but not the graph. SWAP POINT: the merge that
    brings graph.apply_confirmed; replace this class with an adapter over that facade."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object]] = []  # a recording fake, for tests

    def apply_confirmed(self, cluster_id: str, location_id: str, at: object) -> bool:
        self.calls.append((cluster_id, location_id, at))
        logger.warning(
            "graph.apply_confirmed is not available yet; the officer's confirmation was recorded "
            "on the outcome only",
            cluster_id=cluster_id,
            location_id=location_id,
        )
        return False
