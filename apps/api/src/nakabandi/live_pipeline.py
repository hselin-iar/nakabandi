"""The LIVE complaint chain: real facades behind the pipeline's ports (DOC 2 §2.1, DOC 3 M2).

`pipeline.ProcessComplaint` only knows small ports (`resolve`, `context_for`, `generate`, `assess`,
`raise_or_merge`). The real graph, forecast and interception facades speak different shapes, and
something has to translate between them: that is this file. It is the one place, besides
`pipeline` and `main.py`, that sees several modules at once.

    graph.resolve            <- every account the complaint reached (layer 1 + hops)
    graph.context_for        -> a forecast ClusterContext, built with intake + the registry
    forecast.generate        <- registry locations, home district, this cluster's past delays
    interception.assess      <- the top location targets, traced accounts, disputed and held paise
    alerting.raise_or_merge  <- the real AlertService

`build_pipeline` is also what Track B's evaluation harness injects ("the real pipeline is injected
from main.py at compose time"), so the evaluation replays the SAME chain the API runs."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import structlog
from sqlalchemy.orm import Session

from nakabandi.forecast import (
    ClusterContext,
    Forecast,
    Forecaster,
    GlobalCashoutIndex,
    LocationInfo,
)
from nakabandi.forecast.infrastructure.repositories import SqlForecastRepo
from nakabandi.geo import GeoService
from nakabandi.graph import ClusterService, compute_footprint
from nakabandi.graph.domain.types import LocationStat
from nakabandi.graph.infrastructure.repositories import SqlClusterRepo
from nakabandi.intake import LienContextLookup
from nakabandi.intake.infrastructure.repositories import SqlComplaintRepo
from nakabandi.interception import Interceptor, TargetRef
from nakabandi.interception.domain.units import Unit as InterceptionUnit
from nakabandi.interception.infrastructure.repositories import SqlAssessmentRepo
from nakabandi.pipeline import ProcessComplaint
from nakabandi.shared import EventBus, Id, Policy, SimTime

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# The registry, read once and shared (rebuilt only when a registry snapshot lands)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RegistrySnapshot:
    locations: list[LocationInfo] = field(default_factory=list)
    by_id: dict[Id, LocationInfo] = field(default_factory=dict)
    units: list[InterceptionUnit] = field(default_factory=list)

    def coords(self) -> dict[Id, tuple[float, float]]:
        return {i: (loc.lat, loc.lon) for i, loc in self.by_id.items()}


class RegistryCache:
    """Process-wide cache of the registry the forecast chain reads on every complaint. Building
    it walks every location, so it is built lazily and dropped by IngestHooks.on_registry."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshot: RegistrySnapshot | None = None

    def invalidate(self) -> None:
        with self._lock:
            self._snapshot = None

    def get(self, session: Session) -> RegistrySnapshot:
        with self._lock:
            if self._snapshot is None:
                geo = GeoService(session)
                locations = [
                    LocationInfo(
                        id=loc.id,
                        cell_id=loc.cell_id,
                        district_id=loc.district_id,
                        bank_id=loc.bank_id,
                        lat=loc.lat,
                        lon=loc.lon,
                        channel=loc.kind,
                        activity_index=loc.activity_index,
                    )
                    for loc in geo.locations(limit=1_000_000)
                ]
                units = [
                    InterceptionUnit(id=u.id, kind=u.kind, lat=u.lat, lon=u.lon)
                    for u in geo.units()
                    if u.status == "active"
                ]
                self._snapshot = RegistrySnapshot(
                    locations=locations, by_id={loc.id: loc for loc in locations}, units=units
                )
            return self._snapshot


# ---------------------------------------------------------------------------
# graph -> forecast
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LiveContext:
    """What `context_for` hands `generate`: the forecast's own context plus the three inputs the
    Forecaster takes beside it."""

    forecast_ctx: ClusterContext
    home_district_id: Id
    delays_min: list[float]


class LiveClusterPort:
    def __init__(
        self,
        cluster: ClusterService,
        intake: LienContextLookup,
        registry: Callable[[], RegistrySnapshot],
    ) -> None:
        self._cluster = cluster
        self._intake = intake
        self._registry = registry

    def resolve(self, accounts: list[Id], as_of: SimTime) -> Any:
        return self._cluster.resolve(accounts, as_of)

    def context_for(self, complaint_id: Id, cluster_id: Id, as_of: SimTime) -> LiveContext:
        detail = self._intake.complaint_detail(complaint_id)
        if detail is None:
            raise LookupError(f"complaint {complaint_id!r} not found")
        registry = self._registry()
        graph_ctx = self._cluster.context_for(cluster_id, as_of)

        # Cash-out history of the cluster, as the forecast wants it. graph's own
        # PointInTimeStats.observation_count counts location ROWS, so totals are summed here.
        stats: list[LocationStat] = graph_ctx.location_stats
        location_counts = {s.location_id: s.observation_count for s in stats}
        cell_counts: dict[Id, int] = {}
        channel_counts: dict[str, int] = {}
        for s in stats:
            cell_counts[s.cell_id] = cell_counts.get(s.cell_id, 0) + s.observation_count
            loc = registry.by_id.get(s.location_id)
            if loc is not None:
                channel_counts[loc.channel] = (
                    channel_counts.get(loc.channel, 0) + s.observation_count
                )
        footprint = graph_ctx.footprint or compute_footprint(stats, registry.coords())

        home = registry.by_id.get(detail.layer1_home_location_id or "")
        home_district = (
            detail.layer1_home_district_id
            or (home.district_id if home is not None else None)
            or detail.victim_district_id
        )
        delays = self._intake.cluster_delays_min(self._intake.accounts_of(complaint_id), as_of)
        elapsed = max(0.0, (as_of - detail.reported_event_at) / timedelta(minutes=1))

        global_index = GlobalCashoutIndex(self._intake.all_cashout_events())
        global_snap = global_index.snapshot_at(as_of)

        return LiveContext(
            forecast_ctx=ClusterContext(
                complaint_id=complaint_id,
                cluster_id=cluster_id,
                as_of=as_of,
                amount_paise=detail.amount_paise,
                reported_at=detail.reported_event_at,
                layer1_account_id=detail.layer1_account_id,
                layer1_bank_id=detail.layer1_bank_id,
                layer1_home_lat=home.lat if home is not None else None,
                layer1_home_lon=home.lon if home is not None else None,
                unique_accounts=graph_ctx.stats.unique_accounts,
                total_cashout_paise=sum(s.total_paise for s in stats),
                cashout_channel_counts=channel_counts,
                cashout_location_counts=location_counts,
                cashout_cell_counts=cell_counts,
                cashout_location_recency={},
                centroid_lat=footprint.centroid_lat if footprint else None,
                centroid_lon=footprint.centroid_lon if footprint else None,
                radius_km=footprint.radius_km if footprint else 0.0,
                prior_cashout_count=sum(location_counts.values()),
                elapsed_min=elapsed,
                global_cashout_location_counts=global_snap.location_counts,
                global_cashout_total=global_snap.total,
                global_n_locations=len(registry.by_id),
            ),
            home_district_id=home_district,
            delays_min=delays,
        )


class LiveForecaster:
    def __init__(self, forecaster: Forecaster, registry: Callable[[], RegistrySnapshot]) -> None:
        self._forecaster = forecaster
        self._registry = registry

    def generate(self, ctx: LiveContext, as_of: SimTime) -> Forecast:
        return self._forecaster.generate(
            ctx.forecast_ctx,
            self._registry().locations,
            ctx.home_district_id,
            ctx.delays_min,
            as_of,
        )


# ---------------------------------------------------------------------------
# forecast -> interception
# ---------------------------------------------------------------------------


class LiveInterceptor:
    """Assess the forecast's top LOCATION targets. If the location level abstained there is no
    location to send anyone to: no targets, no assessments, no alert (monitor only)."""

    def __init__(
        self,
        interceptor: Interceptor,
        intake: LienContextLookup,
        registry: Callable[[], RegistrySnapshot],
        active_holds: Callable[[Id], dict[Id, int]],
        policy: Policy,
    ) -> None:
        self._interceptor = interceptor
        self._intake = intake
        self._registry = registry
        self._active_holds = active_holds
        self._policy = policy

    def assess(self, forecast: Forecast, complaint_id: Id, now: SimTime) -> list[Any]:
        level = forecast.levels.get("location")
        if level is None or level.abstained or not level.items:
            return []
        registry = self._registry()
        targets = []
        for item in sorted(level.items, key=lambda i: i.rank)[: self._policy.interception.targets]:
            loc = registry.by_id.get(item.id)
            if loc is None:
                continue
            # confidence: THIS target's probability (the ladder's "min confidence for action" asks
            # how sure we are about the target, not about the district)
            targets.append(
                (
                    TargetRef(kind="location", id=loc.id),
                    loc.channel,
                    loc.lat,
                    loc.lon,
                    item.prob,
                    forecast.timing,
                )
            )
        if not targets:
            return []
        return self._interceptor.assess(
            forecast.id,
            targets,
            complaint_id,
            self._intake.accounts_of(complaint_id),
            self._intake.disputed_by_account(complaint_id),
            self._active_holds(complaint_id),
            now,
        )


class GeoUnitRepo:
    """interception.UnitRepo over the cached registry (geo owns the units table, LC-10; the
    interception module's own SqlUnitRepo reads a table of its own that nothing creates)."""

    def __init__(self, registry: Callable[[], RegistrySnapshot]) -> None:
        self._registry = registry

    def all_units(self) -> list[InterceptionUnit]:
        return list(self._registry().units)


# ---------------------------------------------------------------------------
# The factory
# ---------------------------------------------------------------------------


def build_pipeline(
    session: Session,
    *,
    policy: Policy,
    bus: EventBus,
    registry_cache: RegistryCache,
    alert_service: Any,
    model_store: Any | None = None,
    metrics: Any | None = None,
) -> ProcessComplaint:
    """A ProcessComplaint over the REAL facades, on `session`. main.py builds one per unit of work;
    the evaluation harness (Track B) calls it too, so both run the same chain.

    `alert_service` is an alerting.AlertService on the same session (main.py builds it with the
    same wiring the alert routes use). `model_store` is forecast v1's, when there is one."""
    registry = lambda: registry_cache.get(session)  # noqa: E731
    intake = LienContextLookup(session)
    forecaster_kwargs: dict[str, Any] = {}
    if model_store is not None:
        forecaster_kwargs["model_store"] = model_store
    return ProcessComplaint(
        complaint_repo=SqlComplaintRepo(session),
        cluster_service=LiveClusterPort(
            ClusterService(SqlClusterRepo(session), bus), intake, registry
        ),
        forecaster=LiveForecaster(
            Forecaster(SqlForecastRepo(session), policy, **forecaster_kwargs), registry
        ),
        interceptor=LiveInterceptor(
            Interceptor(GeoUnitRepo(registry), SqlAssessmentRepo(session), policy),  # type: ignore[arg-type]
            intake,
            registry,
            alert_service.active_hold_totals,
            policy,
        ),
        alert_service=alert_service,
        bus=bus,
        metrics=metrics,
    )
