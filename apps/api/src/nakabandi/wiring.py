"""Adapters that let one module read another through its facade, wired in main.py (DOC 2 §2.6:
only `pipeline` and `main.py` see several modules at once). Each is built per request on that
request's session, so a projector reads what the publisher just wrote."""

from __future__ import annotations

from collections.abc import Callable
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
from nakabandi.geo import GeoService, LocationScopeLookup
from nakabandi.graph import ClusterService
from nakabandi.graph.infrastructure.repositories import SqlClusterRepo
from nakabandi.intake import LienContextLookup
from nakabandi.interception.infrastructure.repositories import SqlAssessmentRepo
from nakabandi.shared import EventBus

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


class AlertDetailSourceAdapter:
    """alerting.AlertDetailSource over the forecast and interception modules."""

    def __init__(self, session: Session) -> None:
        self._forecasts = SqlForecastRepo(session)
        self._assessments = SqlAssessmentRepo(session)

    def forecast(self, forecast_id: str) -> object | None:
        return self._forecasts.get_by_id(forecast_id)

    def assessments(self, forecast_id: str) -> list[object]:
        return list(self._assessments.get_by_forecast(forecast_id))


class GraphConfirmedCashOut:
    """alerting.ConfirmedCashOutPort over graph.apply_confirmed (DOC 3 S3): an officer-confirmed
    cash-out location becomes an observation at `at` in the cluster's affinity, so the NEXT forecast
    for that cluster sees it immediately, without waiting for a lagged bank report."""

    def __init__(self, session: Session, bus_factory: Callable[[Session], EventBus]) -> None:
        self._session = session
        self._bus_factory = bus_factory

    def apply_confirmed(self, cluster_id: str, location_id: str, at: object) -> bool:
        where = LocationScopeLookup(self._session).for_location(location_id)
        if where is None or where.cell_id is None:
            return False
        ClusterService(
            SqlClusterRepo(self._session), self._bus_factory(self._session)
        ).apply_confirmed(
            cluster_id,
            location_id,
            where.cell_id,
            where.district_id,
            at,  # type: ignore[arg-type]
        )
        return True
