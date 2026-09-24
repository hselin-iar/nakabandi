"""ProjectForecastMass and ProjectAlertChange: event subscribers that keep heat_rollups current
(DOC 3 M3 application/). Read models come from events only.

Two layers, two sources:
  potential  <- ForecastGenerated : every forecast's cell and location mass, alert_count = 1 per
                forecast (a "contributing forecast", so suppression can hide a lone complaint)
  live       <- AlertRaised       : the alert's target location only (cells and districts are
                summed up from locations at query time, so a cell's mass is never counted twice
                when two alerts share it), alert_count = 1

AlertUpdated is not projected: a merge would add mass again and an expiry would have to remove it,
and neither can be done exactly without remembering what each alert contributed (a per-alert
ledger table, which LC-10 does not list). A live window ages alerts out by hour instead."""

from __future__ import annotations

from collections.abc import Callable

import structlog

from nakabandi.analytics.application.ports import ProjectionSource, RollupDelta, RollupRepo
from nakabandi.analytics.domain.heat import Layer
from nakabandi.analytics.domain.rollup import band_of, bucket_hour, mass_from_forecast
from nakabandi.shared import AlertRaised, ForecastGenerated, Policy

logger = structlog.get_logger(__name__)

UNKNOWN_CATEGORY = "unknown"

PROJECTED_ITEMS_PER_LEVEL = 25
"""A forecast ranks up to ~200 candidate locations; the heatmap only ever shows the ones with
real mass. Each level's top items by mass are projected and the long tail is not: it holds a
negligible share of the probability, and writing it made every complaint cost two hundred rows
(the A11 stress run: the projector was 78% of a complaint's time and grew the table without
bound). Named here, not in policy.yaml, because LC-7's keys are frozen."""


def _top_items(items: list) -> list:
    """The level's top PROJECTED_ITEMS_PER_LEVEL MassItems, per kind, by mass."""
    kept = []
    for kind in ("cell", "location"):
        of_kind = sorted((i for i in items if i.target_kind == kind), key=lambda i: -i.mass)
        kept.extend(of_kind[:PROJECTED_ITEMS_PER_LEVEL])
    return kept


class ProjectForecastMass:
    def __init__(
        self,
        source: ProjectionSource,
        repo: RollupRepo,
        policy: Policy,
        on_version: Callable[[int], None],
    ) -> None:
        self._source = source
        self._repo = repo
        self._policy = policy
        self._on_version = on_version

    def handle(self, event: ForecastGenerated) -> None:
        facts = self._source.forecast_facts(event.complaint_id)
        if facts is None:
            logger.warning("analytics.forecast_missing", complaint_id=event.complaint_id)
            return
        complaint = self._source.complaint_facts(event.complaint_id)
        heat = self._policy.heatmap
        category = complaint.category if complaint else UNKNOWN_CATEGORY
        amount_band = band_of(complaint.amount_paise, heat.amount_bands) if complaint else 0
        deltas = [
            RollupDelta(
                target_kind=item.target_kind,
                target_id=item.target_id,
                hour_bucket=bucket_hour(facts.generated_at),
                category=category,
                amount_band=amount_band,
                confidence_band=band_of(facts.confidence, heat.confidence_bands),
                layer=Layer.POTENTIAL.value,
                mass=item.mass,
                alert_count=1,
            )
            for item in _top_items(mass_from_forecast(facts))
        ]
        if deltas:
            self._on_version(self._repo.add(deltas))


class ProjectAlertChange:
    def __init__(
        self,
        source: ProjectionSource,
        repo: RollupRepo,
        policy: Policy,
        on_version: Callable[[int], None],
    ) -> None:
        self._source = source
        self._repo = repo
        self._policy = policy
        self._on_version = on_version

    def handle(self, event: AlertRaised) -> None:
        alert = self._source.alert_facts(event.alert_id)
        if alert is None:
            logger.warning("analytics.alert_missing", alert_id=event.alert_id)
            return
        facts = self._source.forecast_facts(alert.complaint_id)
        complaint = self._source.complaint_facts(alert.complaint_id)
        heat = self._policy.heatmap
        # The alert's own location's share of the forecast; 0 if the forecast did not rank it.
        mass = 0.0
        if facts is not None:
            mass = next(
                (
                    m.mass
                    for m in mass_from_forecast(facts)
                    if m.target_kind == "location" and m.target_id == alert.target_id
                ),
                0.0,
            )
        delta = RollupDelta(
            target_kind="location",
            target_id=alert.target_id,
            hour_bucket=bucket_hour(alert.created_at),
            category=complaint.category if complaint else UNKNOWN_CATEGORY,
            amount_band=band_of(complaint.amount_paise, heat.amount_bands) if complaint else 0,
            confidence_band=band_of(facts.confidence, heat.confidence_bands) if facts else 0,
            layer=Layer.LIVE.value,
            mass=mass,
            alert_count=1,
        )
        self._on_version(self._repo.add([delta]))
