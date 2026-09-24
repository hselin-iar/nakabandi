"""RaiseOrMergeAlert use case (DOC 3 M4).

Processes a Forecast + list[InterceptAssessment] from the pipeline:
  - For each qualifying target (ladder_level != NONE, confidence >= floor):
    - Find open alert by dedup_key → merge; else create (the alert is anchored to the
      complaint of the forecast that raised it, and keeps that anchor when later merges arrive)
  - Apply budget ranking and timer scheduling in the same unit of work.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from nakabandi_contracts.enums import AlertStatus, LadderLevel

from nakabandi.alerting.application.ports import AlertRepo, TargetScopePort
from nakabandi.alerting.domain.alert import Alert, TimelineEntry
from nakabandi.alerting.domain.budget import priority as compute_priority
from nakabandi.alerting.domain.budget import queue_key, rank_and_cap
from nakabandi.alerting.domain.dedup import dedup_key
from nakabandi.alerting.domain.severity import severity
from nakabandi.shared import Clock, Id, Policy, SimTime, new_id

logger = structlog.get_logger(__name__)


@dataclass
class AlertResult:
    """Result returned to the pipeline (DOC 3 process_complaint Stage 5)."""

    alert_id: Id | None  # None if all assessments were below floor
    created: bool  # True = new alert, False = merged into existing
    alert_ids: list[Id]  # All alerts raised/merged in this call
    created_ids: list[Id] = field(default_factory=list)  # the subset that are new


class RaiseOrMergeAlert:
    """DOC 3 M4:
    for each target that qualifies (ladder level != NONE and confidence >= alert floor):
      find an open alert by dedup_key; if found, merge; else create.
      Then routing, budget ranking, timers — all in one transaction.
    """

    def __init__(
        self,
        alert_repo: AlertRepo,
        policy: Policy,
        clock: Clock,
        scope_lookup: TargetScopePort | None = None,
        on_created: Callable[[Alert], None] | None = None,
        amount_of: Callable[[Id], int | None] | None = None,
    ) -> None:
        self._repo = alert_repo
        self._policy = policy
        self._clock = clock
        self._scope_lookup = scope_lookup
        self._on_created = on_created
        self._amount_of = amount_of

    def run(self, forecast: Any, assessments: list[Any]) -> AlertResult:
        """Process assessments and raise or merge alerts.

        forecast: nakabandi.forecast.Forecast (LC-4 shape)
        assessments: list[nakabandi.interception.InterceptAssessment]
        """
        now: SimTime = self._clock.now()
        floor: float = self._policy.alerting.floor_confidence
        expire_grace_min: float = self._policy.alerting.expire_grace_min
        dedup_window_min: float = self._policy.alerting.dedup_window_min

        raised: list[Alert] = []
        alert_ids: list[Id] = []
        first_alert_id: Id | None = None
        first_created: bool = False

        for assessment in assessments:
            # Skip non-qualifying assessments (DOC 3 M4)
            if assessment.ladder_level == LadderLevel.NONE:
                continue
            confidence = self._confidence(forecast, assessment)
            if confidence < floor:
                continue

            dk = dedup_key(
                forecast.cluster_id,
                assessment.target.kind,
                assessment.target.id,
            )

            existing: Alert | None = self._repo.get_by_dedup_key(dk)

            if existing is not None and existing.status in (
                AlertStatus.OPEN,
                AlertStatus.ESCALATED,
                AlertStatus.ACKNOWLEDGED,
            ):
                # --- Merge ---
                entry = TimelineEntry(
                    id=new_id(),
                    alert_id=existing.id,
                    at=now,
                    kind="merged",
                    actor_id=None,
                    text_code="alert.merged",
                    text_params={"forecast_id": forecast.id},
                )
                window_end = now + timedelta(minutes=dedup_window_min)
                existing.merge(
                    forecast_id=forecast.id,
                    confidence=confidence,
                    window_end=window_end,
                    expires_at=window_end + timedelta(minutes=expire_grace_min),
                    entry=entry,
                )
                self._repo.save(existing)
                alert_ids.append(existing.id)
                if first_alert_id is None:
                    first_alert_id = existing.id
                    first_created = False
            else:
                # --- Create ---
                window_end = now + timedelta(minutes=dedup_window_min)
                expires_at = window_end + timedelta(minutes=expire_grace_min)
                amount = self._amount(forecast)
                sev = severity(
                    confidence=confidence,
                    amount_paise=amount,
                    verdict=assessment.verdict,
                    policy=self._policy,
                )
                alert_id = new_id()
                scope = (
                    self._scope_lookup.for_location(assessment.target.id)
                    if self._scope_lookup is not None
                    else None
                )
                init_entry = TimelineEntry(
                    id=new_id(),
                    alert_id=alert_id,
                    at=now,
                    kind="raised",
                    actor_id=None,
                    text_code="alert.raised",
                    text_params={"forecast_id": forecast.id},
                )
                new_alert = Alert(
                    id=alert_id,
                    cluster_ref=forecast.cluster_id,
                    target_kind=(scope.kind if scope is not None and scope.kind else None)
                    or assessment.target.kind,
                    target_id=assessment.target.id,
                    target_name=getattr(assessment.target, "name", None)
                    or (scope.name if scope is not None and scope.name else assessment.target.id),
                    dedup_key=dk,
                    severity=sev,
                    confidence=confidence,
                    status=AlertStatus.OPEN,
                    ladder_level=assessment.ladder_level,
                    is_deferred=False,
                    is_probe=False,
                    window_start=now,
                    window_end=window_end,
                    expires_at=expires_at,
                    created_at=now,
                    forecast_id=forecast.id,
                    complaint_id=forecast.complaint_id,
                    masked=False,
                    scope_state_id=scope.state_id if scope is not None else None,
                    scope_district_id=scope.district_id if scope is not None else None,
                    scope_bank_id=scope.bank_id if scope is not None else None,
                    priority=compute_priority(
                        confidence,
                        amount,
                        self._interception_probability(assessment),
                    ),
                    timeline=[init_entry],
                )
                self._repo.save(new_alert)
                raised.append(new_alert)
                alert_ids.append(alert_id)
                if first_alert_id is None:
                    first_alert_id = alert_id
                    first_created = True

        # Budget: rank each new alert against the others in its queue (jurisdiction x shift).
        # There are no timers to set: escalation, expiry and the miss are found in the database
        # when they fall due (timers.py).
        for a in raised:
            self._rank_queue(a)
        for a in raised:
            if self._on_created is not None:
                self._on_created(a)

        logger.info(
            "alerting.raise_or_merge.done",
            raised=len(raised),
            total=len(alert_ids),
        )
        return AlertResult(
            alert_id=first_alert_id,
            created=first_created,
            alert_ids=alert_ids,
            created_ids=[a.id for a in raised],
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _confidence(forecast: Any, assessment: Any) -> float:
        """How sure we are about THIS target: the forecast's probability that the cluster's next
        cash-out is at it (LC-4 item.prob, location level). An InterceptAssessment carries no
        confidence of its own, and the forecast's overall confidence is the district level's,
        near 1.0 for every target, which would make every alert look equally certain. A caller
        that supplies a confidence per assessment still wins."""
        own = getattr(assessment, "confidence", None)
        if own is not None:
            return float(own)
        level = getattr(forecast, "levels", {}).get("location")
        if level is not None and not level.abstained:
            for item in level.items:
                if item.id == assessment.target.id:
                    return float(item.prob)
        return float(getattr(forecast, "confidence", 0.0))

    def _amount(self, forecast: Any) -> int:
        """The complaint's amount. A Forecast does not carry it (it belongs to the complaint), so
        it is looked up through intake; a caller that does pass `amount_paise` still wins."""
        direct = getattr(forecast, "amount_paise", None)
        if direct is not None:
            return int(direct)
        if self._amount_of is not None:
            looked_up = self._amount_of(forecast.complaint_id)
            if looked_up is not None:
                return int(looked_up)
        return 0

    def _interception_probability(self, assessment: Any) -> float:
        """The assessment's own probability that a unit arrives first; if a caller's assessment
        has none, the policy floor (the same floor severity() uses)."""
        p = getattr(assessment, "interception_probability", None)
        return float(p) if p is not None else self._policy.interception.thresholds.marginal

    def _rank_queue(self, alert: Alert) -> None:
        """Rank this alert's queue for its shift and save every member whose place changed."""
        district, shift = queue_key(alert, self._policy)
        shift_seconds = self._policy.alerting.shift_hours * 3600
        start = datetime.fromtimestamp(shift * shift_seconds, tz=UTC)
        peers = self._repo.list_queue_entries(
            None if district == "unscoped" else district,
            start,
            start + timedelta(seconds=shift_seconds),
        )
        before = {p.id: (p.is_deferred, p.is_probe) for p in peers}
        rank_and_cap(peers, self._policy)
        for peer in peers:
            # `budget_rank` is the alert's place WHEN RAISED: one higher-priority arrival shifts
            # every place below it, so keeping it current would rewrite the whole queue on every
            # raise (O(alerts) writes: the A11 stress run). Nothing reads it; what other alerts
            # need is the flags, and those change only near the budget line.
            if peer.id == alert.id or before[peer.id] != (peer.is_deferred, peer.is_probe):
                self._repo.save_budget(peer)
