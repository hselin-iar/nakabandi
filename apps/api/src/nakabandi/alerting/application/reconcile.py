"""ReconcileOutcome (DOC 3 M4): decide what became of each alert.

  hit   an observation at the alert's target location within [window_start, window_end]
  late  an observation after window_end, within outcome.grace_hours
  miss  window_end + grace passed with neither: decided by a TIMER, never by data arriving

An alert gets one reconciled outcome. An officer's outcome (MarkOutcome) is a separate row that may
disagree; the alert shows both."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import structlog

from nakabandi.alerting.application.ports import AlertRepo, ObservationSource, OutcomeRepo
from nakabandi.alerting.domain.alert import Alert, TimelineEntry
from nakabandi.alerting.domain.outcome import Outcome, classify_outcome
from nakabandi.shared import Clock, Id, ObservationIngested, Policy, new_id

logger = structlog.get_logger(__name__)


class ReconcileOutcome:
    def __init__(
        self,
        alert_repo: AlertRepo,
        outcome_repo: OutcomeRepo,
        observations: ObservationSource | None,
        policy: Policy,
        clock: Clock,
        on_outcome: Callable[[Alert, Outcome], None] | None = None,
    ) -> None:
        self._alerts = alert_repo
        self._outcomes = outcome_repo
        self._observations = observations
        self._policy = policy
        self._clock = clock
        self._on_outcome = on_outcome

    # ---- data-driven: hit / late ----------------------------------------------------------

    def on_observation(self, event: ObservationIngested) -> list[Outcome]:
        """ObservationIngested handler: match each new cash-out to the alerts that predicted its
        location and are still undecided."""
        if self._observations is None:
            return []
        decided: list[Outcome] = []
        now = self._clock.now()
        for obs in self._observations.observations(event.observation_ids):
            for alert in self._alerts.list_awaiting_outcome(target_id=obs.location_id):
                outcome = classify_outcome(alert, obs.event_at, now, obs.id, self._policy, new_id())
                if outcome is None:
                    continue  # outside the window and its grace: says nothing about this alert
                self._record(alert, outcome)
                decided.append(outcome)
        return decided

    # ---- timer-driven: miss ---------------------------------------------------------------

    def fire_due(self) -> int:
        """Decide the misses that are due: alerts whose window + grace ended with no reconciled
        outcome. Whatever their status (an expired alert still gets its miss)."""
        cutoff = self._clock.now() - timedelta(hours=self._policy.outcome.grace_hours)
        ids = self._alerts.list_miss_due_ids(cutoff, 200)
        for alert_id in ids:
            self._fire(alert_id)
        return len(ids)

    def _fire(self, alert_id: Id) -> None:
        alert = self._alerts.get_by_id(alert_id)
        if alert is None or self._has_reconciled(alert_id):
            return
        outcome = classify_outcome(alert, None, self._clock.now(), None, self._policy, new_id())
        if outcome is not None:
            self._record(alert, outcome)

    def _has_reconciled(self, alert_id: Id) -> bool:
        return any(o.source == "reconciled" for o in self._outcomes.list_for_alert(alert_id))

    def _record(self, alert: Alert, outcome: Outcome) -> None:
        self._outcomes.save(outcome)
        alert.timeline.append(
            TimelineEntry(
                id=new_id(),
                alert_id=alert.id,
                at=outcome.decided_at,
                kind="outcome",
                actor_id=None,
                text_code=f"alert.outcome.{outcome.result}",
                text_params={"source": outcome.source},
            )
        )
        self._alerts.save(alert)
        logger.info("alerting.outcome", alert_id=alert.id, result=outcome.result)
        if self._on_outcome is not None:
            self._on_outcome(alert, outcome)
