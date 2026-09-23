"""QueryHeatmap, QueryTimeseries, QueryLiveMetrics (DOC 3 M3 application/).

They read rollups only, restricted to the principal's scope; the registry catalog is used to place
targets (district / cell / location, coordinates) and to apply scope and bbox."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Mapping, Set
from datetime import timedelta

from nakabandi_contracts.enums import Permission, Role

from nakabandi.access import Principal, authorize
from nakabandi.analytics.application.ports import (
    BucketSum,
    GeoCatalog,
    GeoCatalogPort,
    RollupRepo,
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
from nakabandi.analytics.domain.potential import decayed_intensity
from nakabandi.analytics.domain.rollup import band_of, bucket_hour
from nakabandi.analytics.domain.suppress import apply_k_threshold
from nakabandi.shared import Clock, Forbidden, Policy, SimTime, ValidationFailed

LIVE_WINDOW = timedelta(hours=24)
UNIT = "expected cash-out mass"
LIVE_NOTE = "Expected cash-out mass behind alerts raised in this window."
POTENTIAL_NOTE = (
    "Persistence estimate of recent forecast intensity over the next 72 h; not a separate model."
)


class _Visibility:
    """Which registry targets a principal (and the requested state / district) may see."""

    def __init__(self, principal: Principal, filters: HeatFilters, catalog: GeoCatalog) -> None:
        scope = principal.scope
        self._bank = scope.bank_id
        district = filters.district
        state = filters.state
        if scope.bank_id is None:
            if scope.district_id is not None:
                if district is not None and district != scope.district_id:
                    raise Forbidden("FORBIDDEN_SCOPE", "district is outside your scope")
                district = scope.district_id
            elif scope.state_id is not None:
                if state is not None and state != scope.state_id:
                    raise Forbidden("FORBIDDEN_SCOPE", "state is outside your scope")
                state = scope.state_id
        self._district = district
        self._state = state
        self._bbox = filters.bbox
        self._catalog = catalog

    def _ok(
        self, district_id: str, state_id: str | None, lat: float, lon: float, bank_id: str | None
    ) -> bool:
        if self._bank is not None and bank_id != self._bank:
            return False
        if self._district is not None and district_id != self._district:
            return False
        if self._state is not None and state_id != self._state:
            return False
        if self._bbox is not None:
            min_lon, min_lat, max_lon, max_lat = self._bbox
            if not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
                return False
        return True

    def location(self, location_id: str) -> bool:
        loc = self._catalog.locations.get(location_id)
        return loc is not None and self._ok(
            loc.district_id, loc.state_id, loc.lat, loc.lon, loc.bank_id
        )

    def cell(self, cell_id: str) -> bool:
        cell = self._catalog.cells.get(cell_id)
        # A bank-scoped principal never sees a cell: it aggregates other banks' locations.
        return (
            cell is not None
            and self._bank is None
            and self._ok(cell.district_id, cell.state_id, cell.lat, cell.lon, None)
        )


def _validate(filters: HeatFilters, policy: Policy, window: tuple[SimTime, SimTime]) -> None:
    problems: list[dict] = []
    if window[0] > window[1]:
        problems.append({"field": "from", "issue": "from must not be after to"})
    n_bands = len(policy.heatmap.amount_bands)
    if filters.amount_band is not None and not 0 <= filters.amount_band <= n_bands:
        problems.append({"field": "amount_band", "issue": f"must be 0..{n_bands}"})
    if filters.min_confidence is not None and not 0.0 <= filters.min_confidence <= 1.0:
        problems.append({"field": "min_confidence", "issue": "must be between 0 and 1"})
    if problems:
        raise ValidationFailed("HEAT_FILTER_INVALID", "invalid heatmap filters", problems)


class _Base:
    def __init__(
        self,
        repo: RollupRepo,
        catalog: GeoCatalogPort,
        policy: Policy,
        clock: Clock,
        role_permissions: Mapping[Role, Set[Permission]],
    ) -> None:
        self._repo = repo
        self._catalog = catalog
        self._policy = policy
        self._clock = clock
        self._role_perms = role_permissions

    def window(self, filters: HeatFilters) -> tuple[SimTime, SimTime]:
        to = filters.to or self._clock.now()
        return (filters.from_ or to - LIVE_WINDOW), to

    def _rows(
        self, filters: HeatFilters, kind: str, window: tuple[SimTime, SimTime]
    ) -> list[BucketSum]:
        min_band = (
            band_of(filters.min_confidence, self._policy.heatmap.confidence_bands)
            if filters.min_confidence is not None
            else None
        )
        return self._repo.window(
            layer=filters.layer.value,
            target_kind=kind,
            from_bucket=bucket_hour(window[0]),
            to_bucket=bucket_hour(window[1]),
            category=filters.category,
            amount_band=filters.amount_band,
            min_confidence_band=min_band,
        )


class QueryHeatmap(_Base):
    def etag(self, filters: HeatFilters, principal: Principal) -> str:
        """Weak ETag from the rollup version plus everything else the answer depends on: the
        filters, the principal's scope, and the hour window (the potential layer also decays with
        time, so an unchanged version still changes value as the hour turns)."""
        window = self._effective_window(filters)
        parts = [
            filters.layer.value,
            filters.level.value,
            str(bucket_hour(window[0])),
            str(bucket_hour(window[1])),
            filters.state or "",
            filters.district or "",
            filters.category or "",
            str(filters.amount_band),
            str(filters.min_confidence),
            str(filters.bbox),
            str(principal.scope),
            str(principal.role.value),
        ]
        digest = hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]  # noqa: S324 - not security
        return f'W/"{self._repo.current_version()}-{digest}"'

    def _effective_window(self, filters: HeatFilters) -> tuple[SimTime, SimTime]:
        from_, to = self.window(filters)
        if filters.layer is Layer.POTENTIAL:
            from_ = to - timedelta(hours=self._policy.heatmap.potential_lookback_hours)
        return from_, to

    def run(self, filters: HeatFilters, principal: Principal) -> HeatmapResult:
        authorize(principal, Permission.VIEW_ALERTS, self._role_perms)
        window = self._effective_window(filters)
        _validate(filters, self._policy, self.window(filters))
        catalog = self._catalog.catalog()
        visible = _Visibility(principal, filters, catalog)
        if principal.scope.bank_id is not None and filters.level is not Level.LOCATION:
            # A bank sees only its own locations; any coarser level mixes in other banks' data.
            raise Forbidden("FORBIDDEN_SCOPE", "a bank scope may only view the location level")

        # Which rollup rows feed which level: live rolls up from locations; potential uses its own
        # cell rows above location level (a forecast's cell and location levels describe the same
        # mass, so mixing them would count it twice).
        kind = (
            "location" if filters.layer is Layer.LIVE or filters.level is Level.LOCATION else "cell"
        )
        rows = self._rows(filters, kind, window)
        per_target = self._sum(rows, filters.layer, window[1])

        cells = self._place(per_target, kind, filters.level, catalog, visible)
        suppressed = 0
        if filters.level is not Level.LOCATION:
            cells, suppressed = apply_k_threshold(cells, self._policy.heatmap.k_threshold)
        cells.sort(key=lambda c: (-c.value, c.id))
        values = [c.value for c in cells]
        return HeatmapResult(
            layer=filters.layer.value,
            level=filters.level.value,
            generated_at=self._clock.now(),
            version=self._repo.current_version(),
            cells=cells,
            suppressed_count=suppressed,
            legend=Legend(
                min=min(values, default=0.0),
                max=max(values, default=0.0),
                unit=UNIT,
                note=POTENTIAL_NOTE if filters.layer is Layer.POTENTIAL else LIVE_NOTE,
            ),
        )

    def _sum(
        self, rows: list[BucketSum], layer: Layer, now: SimTime
    ) -> dict[str, tuple[float, int]]:
        """Per target: the window's mass (live), or its exponentially decayed mass (potential)."""
        by_target: dict[str, list[BucketSum]] = defaultdict(list)
        for r in rows:
            by_target[r.target_id].append(r)
        heat = self._policy.heatmap
        out: dict[str, tuple[float, int]] = {}
        for target, buckets in by_target.items():
            count = sum(b.alert_count for b in buckets)
            if layer is Layer.LIVE:
                out[target] = (sum(b.mass for b in buckets), count)
            else:
                mass = decayed_intensity(
                    ((b.mass, b.hour_bucket) for b in buckets),
                    now,
                    heat.potential_lookback_hours,
                    heat.decay_half_life_hours,
                )
                out[target] = (mass, count)
        return out

    def _place(
        self,
        per_target: dict[str, tuple[float, int]],
        kind: str,
        level: Level,
        catalog: GeoCatalog,
        visible: _Visibility,
    ) -> list[HeatCell]:
        """Turn per-target sums into map cells at the requested level (district roll-up sums the
        member targets and places the district at the mean of its cells' centroids)."""
        if level is Level.LOCATION:
            return [
                HeatCell(
                    id=t,
                    kind="location",
                    name=catalog.locations[t].name,
                    lat=catalog.locations[t].lat,
                    lon=catalog.locations[t].lon,
                    value=mass,
                    alert_count=count,
                )
                for t, (mass, count) in per_target.items()
                if t in catalog.locations and visible.location(t)
            ]

        # Above location level: group targets under a cell (live: via each location's cell).
        grouped: dict[str, list[float]] = defaultdict(lambda: [0.0, 0])
        for t, (mass, count) in per_target.items():
            cell_id = catalog.locations[t].cell_id if kind == "location" else t
            if kind == "location" and t not in catalog.locations:
                continue
            g = grouped[cell_id]
            g[0] += mass
            g[1] += int(count)
        cells = {c: g for c, g in grouped.items() if c in catalog.cells and visible.cell(c)}

        if level is Level.CELL:
            return [
                HeatCell(
                    id=c,
                    kind="cell",
                    name=None,
                    lat=catalog.cells[c].lat,
                    lon=catalog.cells[c].lon,
                    value=g[0],
                    alert_count=int(g[1]),
                )
                for c, g in cells.items()
            ]

        districts: dict[str, list[float]] = defaultdict(lambda: [0.0, 0])
        for c, g in cells.items():
            d = districts[catalog.cells[c].district_id]
            d[0] += g[0]
            d[1] += int(g[1])
        out: list[HeatCell] = []
        for district_id, g in districts.items():
            members = [c for c in catalog.cells.values() if c.district_id == district_id]
            out.append(
                HeatCell(
                    id=district_id,
                    kind="district",
                    name=catalog.district_names.get(district_id),
                    lat=sum(m.lat for m in members) / len(members),
                    lon=sum(m.lon for m in members) / len(members),
                    value=g[0],
                    alert_count=int(g[1]),
                )
            )
        return out


class QueryTimeseries(_Base):
    def run(self, filters: HeatFilters, principal: Principal) -> TimeseriesResult:
        """Mass and alert count per hour for the same filters and scope as the heatmap. Live sums
        location rows; potential sums cell rows (never both: they describe the same mass)."""
        authorize(principal, Permission.VIEW_ALERTS, self._role_perms)
        window = self.window(filters)
        _validate(filters, self._policy, window)
        catalog = self._catalog.catalog()
        visible = _Visibility(principal, filters, catalog)
        kind = "location" if filters.layer is Layer.LIVE or principal.scope.bank_id else "cell"
        per_hour: dict[SimTime, list[float]] = defaultdict(lambda: [0.0, 0])
        for r in self._rows(filters, kind, window):
            ok = visible.location(r.target_id) if kind == "location" else visible.cell(r.target_id)
            if ok:
                g = per_hour[r.hour_bucket]
                g[0] += r.mass
                g[1] += r.alert_count
        return TimeseriesResult(
            layer=filters.layer.value,
            from_=window[0],
            to=window[1],
            version=self._repo.current_version(),
            points=[TimePoint(h, g[0], int(g[1])) for h, g in sorted(per_hour.items())],
        )


class QueryLiveMetrics(_Base):
    def run(self, principal: Principal) -> LiveMetricsResult:
        """A one-glance summary of the live layer over the last 24 sim hours, in scope."""
        authorize(principal, Permission.VIEW_ALERTS, self._role_perms)
        filters = HeatFilters(layer=Layer.LIVE, level=Level.LOCATION)
        window = self.window(filters)
        catalog = self._catalog.catalog()
        visible = _Visibility(principal, filters, catalog)
        mass, count, active = 0.0, 0, set()
        for r in self._rows(filters, "location", window):
            if visible.location(r.target_id):
                mass += r.mass
                count += r.alert_count
                active.add(r.target_id)
        return LiveMetricsResult(
            generated_at=self._clock.now(),
            version=self._repo.current_version(),
            window_hours=LIVE_WINDOW / timedelta(hours=1),
            alert_count=count,
            expected_mass=mass,
            active_locations=len(active),
        )
