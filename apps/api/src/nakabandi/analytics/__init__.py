"""Public facade of the analytics module: what other modules may import (DOC 3 M3).

AnalyticsService is constructed on the caller's SQLAlchemy session, so a projector shares the
publisher's unit of work (its rollup write commits or rolls back with the alert it describes) and
a query reads what that session can see.

Exports:
  AnalyticsService — heatmap(), etag(), timeseries(), live_metrics(), register_projectors()
  HeatFilters, Layer, Level and the result value objects — the query inputs and LC-4 outputs
  ProjectionSource, GeoCatalogPort, GeoCatalog, ... — the ports main.py's wiring implements
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Set

from nakabandi_contracts.enums import Permission, Role
from sqlalchemy import event as sa_event
from sqlalchemy.orm import Session

from nakabandi.access import Principal
from nakabandi.analytics.application.ports import (
    AlertFacts,
    CatalogCell,
    CatalogLocation,
    ComplaintFacts,
    GeoCatalog,
    GeoCatalogPort,
    ProjectionSource,
)
from nakabandi.analytics.application.project import ProjectAlertChange, ProjectForecastMass
from nakabandi.analytics.application.queries import (
    QueryHeatmap,
    QueryLiveMetrics,
    QueryTimeseries,
)
from nakabandi.analytics.domain.heat import (
    HeatCell,
    HeatFilters,
    HeatmapResult,
    Layer,
    Legend,
    Level,
    LiveMetricsResult,
    TimePoint,
    TimeseriesResult,
)
from nakabandi.analytics.domain.rollup import ForecastFacts
from nakabandi.analytics.infrastructure.rollup_repo import SqlRollupRepo
from nakabandi.shared import (
    AlertRaised,
    Clock,
    EventBus,
    ForecastGenerated,
    Policy,
)

__all__ = [
    "AnalyticsService",
    "HeatFilters",
    "HeatCell",
    "HeatmapResult",
    "Layer",
    "Legend",
    "Level",
    "LiveMetricsResult",
    "TimePoint",
    "TimeseriesResult",
    "ForecastFacts",
    "AlertFacts",
    "ComplaintFacts",
    "ProjectionSource",
    "GeoCatalog",
    "GeoCatalogPort",
    "CatalogCell",
    "CatalogLocation",
]


class AnalyticsService:
    def __init__(
        self,
        session: Session,
        *,
        policy: Policy,
        clock: Clock,
        role_permissions: Mapping[Role, Set[Permission]],
        catalog: GeoCatalogPort,
        source: ProjectionSource | None = None,
        publish_version: Callable[[int], None] | None = None,
    ) -> None:
        self._session = session
        self._repo = SqlRollupRepo(session)
        self._source = source
        self._policy = policy
        self._publish_version = publish_version
        args = (self._repo, catalog, policy, clock, role_permissions)
        self._heatmap = QueryHeatmap(*args)
        self._timeseries = QueryTimeseries(*args)
        self._live = QueryLiveMetrics(*args)
        self._pending_version: int | None = None

    # ---- queries (DOC 3 M3: HeatmapService.query, TimeseriesService, LiveMetrics) ----------

    def heatmap(self, filters: HeatFilters, principal: Principal) -> HeatmapResult:
        return self._heatmap.run(filters, principal)

    def etag(self, filters: HeatFilters, principal: Principal) -> str:
        return self._heatmap.etag(filters, principal)

    def timeseries(self, filters: HeatFilters, principal: Principal) -> TimeseriesResult:
        return self._timeseries.run(filters, principal)

    def live_metrics(self, principal: Principal) -> LiveMetricsResult:
        return self._live.run(principal)

    # ---- projectors ------------------------------------------------------------------------

    def register_projectors(self, bus: EventBus) -> None:
        """Subscribe ProjectForecastMass and ProjectAlertChange on `bus`. Their writes ride the
        publisher's session; heat.version is published only AFTER that session commits, so a
        client that refetches on the event always sees the rows."""
        if self._source is None:
            raise RuntimeError("AnalyticsService needs a ProjectionSource to register projectors")
        forecast = ProjectForecastMass(self._source, self._repo, self._policy, self._arm)
        alert = ProjectAlertChange(self._source, self._repo, self._policy, self._arm)
        bus.subscribe(ForecastGenerated, lambda e: forecast.handle(e))  # type: ignore[arg-type]
        bus.subscribe(AlertRaised, lambda e: alert.handle(e))  # type: ignore[arg-type]

    def _arm(self, version: int) -> None:
        first = self._pending_version is None
        self._pending_version = version
        if first and self._publish_version is not None:
            publish = self._publish_version

            def _after_commit(_session: Session) -> None:
                if self._pending_version is not None:
                    publish(self._pending_version)
                self._pending_version = None

            sa_event.listen(self._session, "after_commit", _after_commit, once=True)
