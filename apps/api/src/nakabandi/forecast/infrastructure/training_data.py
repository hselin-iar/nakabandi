"""training_data.py — SqlTrainingDataPort (DOC 3 M2 B6).

The real implementation of `TrainModels.TrainingDataPort` train.py's own docstring described but
never built: nobody had ever actually invoked TrainModels in this codebase before this file
existed, so the forecast chain always ran the v0 heuristic scorer / un-fit timing priors.

Reads through other modules' facades only (graph.ClusterService, intake.LienContextLookup,
geo.GeoService) — this infrastructure file is forecast's own, but forecast may not touch
another module's tables directly (DOC 3 LC-10).
"""

from __future__ import annotations

from nakabandi.forecast.application.train import TrainingDataPort
from nakabandi.forecast.domain.candidates import LocationInfo, generate_candidates
from nakabandi.forecast.domain.global_stats import GlobalCashoutIndex
from nakabandi.forecast.domain.types import Candidate
from nakabandi.forecast.domain.types import ClusterContext as ForecastClusterContext
from nakabandi.geo import GeoService
from nakabandi.graph import ClusterService, compute_footprint
from nakabandi.intake import LienContextLookup
from nakabandi.shared import Id, Policy, SimTime


class _Loc:
    __slots__ = ("id", "cell_id", "district_id", "bank_id", "lat", "lon", "channel")

    def __init__(
        self,
        id: str,
        cell_id: str,
        district_id: str,
        bank_id: str,
        lat: float,
        lon: float,
        channel: str,
    ) -> None:  # noqa: E501
        self.id, self.cell_id, self.district_id = id, cell_id, district_id
        self.bank_id, self.lat, self.lon, self.channel = bank_id, lat, lon, channel


class SqlTrainingDataPort(TrainingDataPort):
    def __init__(
        self,
        cluster_service: ClusterService,
        lien_lookup: LienContextLookup,
        geo_service: GeoService,
        policy: Policy,
    ) -> None:
        self._clusters = cluster_service
        self._lien = lien_lookup
        self._geo = geo_service
        self._policy = policy

    def _registry(self) -> tuple[list[LocationInfo], dict[Id, _Loc]]:
        by_id: dict[Id, _Loc] = {}
        infos: list[LocationInfo] = []
        for loc in self._geo.locations(limit=1_000_000):
            infos.append(
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
            )
            by_id[loc.id] = _Loc(
                loc.id, loc.cell_id, loc.district_id, loc.bank_id, loc.lat, loc.lon, loc.kind
            )
        return infos, by_id

    def _forecast_ctx(
        self,
        complaint,  # ComplaintDetail
        cluster_id: Id,
        as_of: SimTime,
        by_id: dict[Id, _Loc],
        global_index: GlobalCashoutIndex,
        n_locations: int,
    ) -> ForecastClusterContext:
        """Build forecast's per-complaint ClusterContext from graph's cluster-level one — the
        same mapping live_pipeline.py's LiveClusterPort.context_for does for live serving,
        since the two ClusterContext types (graph's vs forecast's) are deliberately different
        shapes, not the same class reused across modules."""
        graph_ctx = self._clusters.context_for(cluster_id, as_of)
        stats = graph_ctx.location_stats
        location_counts = {s.location_id: s.observation_count for s in stats}
        cell_counts: dict[Id, int] = {}
        channel_counts: dict[str, int] = {}
        for s in stats:
            cell_counts[s.cell_id] = cell_counts.get(s.cell_id, 0) + s.observation_count
            loc = by_id.get(s.location_id)
            if loc is not None:
                channel_counts[loc.channel] = (
                    channel_counts.get(loc.channel, 0) + s.observation_count
                )
        footprint = graph_ctx.footprint or compute_footprint(
            stats, {i: (loc.lat, loc.lon) for i, loc in by_id.items()}
        )
        home = by_id.get(complaint.layer1_home_location_id or "")
        global_snap = global_index.snapshot_at(as_of)

        return ForecastClusterContext(
            complaint_id=complaint.id,
            cluster_id=cluster_id,
            as_of=as_of,
            amount_paise=complaint.amount_paise,
            reported_at=complaint.reported_event_at,
            layer1_account_id=complaint.layer1_account_id,
            layer1_bank_id=complaint.layer1_bank_id,
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
            # `as_of` == `reported_at` here (see complaint_records): every training example
            # represents the forecast as it would have looked the moment the complaint arrived,
            # the most common real case (first forecast, generated right at ingestion).
            elapsed_min=max(0.0, (as_of - complaint.reported_event_at).total_seconds() / 60.0),
            global_cashout_location_counts=global_snap.location_counts,
            global_cashout_total=global_snap.total,
            global_n_locations=n_locations,
        )

    def complaint_records(
        self, as_of_end: SimTime
    ) -> list[tuple[ForecastClusterContext, list[Candidate], str]]:
        """(ctx, candidates, actual_location_id) for every complaint whose cluster's money has
        been observed cashing out by as_of_end. `ctx` is bounded to the complaint's OWN
        reported_event_at (not the later cash-out), matching what GenerateForecast would have
        known at the moment it actually ran — the same leakage-free rule cluster_delays_min
        already applies for the timing side."""
        all_locations, by_id = self._registry()
        global_index = GlobalCashoutIndex(self._lien.all_cashout_events())
        n_locations = len(by_id)
        records: list[tuple[ForecastClusterContext, list[Candidate], str]] = []

        for complaint in self._lien.complaints_up_to(as_of_end):
            cluster_id: Id | None = self._clusters.cluster_of(complaint.layer1_account_id)
            if cluster_id is None:
                continue  # innocent / not yet clustered — no candidate set to label

            account_ids = self._clusters.account_ids(cluster_id)
            outcome = self._lien.first_cashout_after(
                account_ids, after=complaint.credited_at, as_of=as_of_end
            )
            if outcome is None:
                continue  # this complaint's cluster hasn't been observed cashing out yet
            actual_location_id, _event_at = outcome

            ctx = self._forecast_ctx(
                complaint,
                cluster_id,
                complaint.reported_event_at,
                by_id,
                global_index,
                n_locations,
            )
            home_district_id = complaint.layer1_home_district_id or complaint.victim_district_id
            candidates = generate_candidates(ctx, all_locations, home_district_id, self._policy)
            if not any(c.location_id == actual_location_id for c in candidates):
                continue  # the real outcome fell outside the candidate radius/cap — unlabelable

            records.append((ctx, candidates, actual_location_id))

        return records

    def delay_records(self, as_of_end: SimTime) -> list[float]:
        """Observed credit-to-cash-out delays (minutes) across every cluster with any account —
        intake.LienContextLookup.cluster_delays_min already implements exactly this, per
        cluster; this just fans it out over every account currently assigned to a cluster."""
        account_ids = self._clusters.all_account_ids()
        return self._lien.cluster_delays_min(account_ids, as_of_end)
