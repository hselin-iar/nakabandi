"""RaiseOrMergeAlert use case (DOC 3 M4).

Processes a Forecast + list[InterceptAssessment] from the pipeline:
  - For each qualifying target (ladder_level != NONE, confidence >= floor):
    - Find open alert by dedup_key → merge; else create (the alert is anchored to the
      complaint of the forecast that raised it, and keeps that anchor when later merges arrive)
  - Apply budget ranking and timer scheduling in the same unit of work.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import structlog
from nakabandi_contracts.enums import AlertStatus, LadderLevel

from nakabandi.alerting.application.ports import AlertRepo, TargetScopePort
from nakabandi.alerting.domain.alert import Alert, TimelineEntry
from nakabandi.alerting.domain.budget import rank_and_cap
from nakabandi.alerting.domain.dedup import dedup_key
from nakabandi.alerting.domain.severity import severity
from nakabandi.shared import Clock, Id, Policy, Scheduler, SimTime, new_id

logger = structlog.get_logger(__name__)


@dataclass
class AlertResult:
    """Result returned to the pipeline (DOC 3 process_complaint Stage 5)."""

    alert_id: Id | None  # None if all assessments were below floor
    created: bool  # True = new alert, False = merged into existing
    alert_ids: list[Id]  # All alerts raised/merged in this call


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
        scheduler: Scheduler,
        escalate_fn: Any,  # EscalateAlert.schedule — injected to avoid circular import
        expire_fn: Any,  # ExpireAlert.schedule
        scope_lookup: TargetScopePort | None = None,
        on_created: Callable[[Alert], None] | None = None,
    ) -> None:
        self._repo = alert_repo
        self._policy = policy
        self._clock = clock
        self._scheduler = scheduler
        self._escalate_fn = escalate_fn
        self._expire_fn = expire_fn
        self._scope_lookup = scope_lookup
        self._on_created = on_created

    def run(self, forecast: Any, assessments: list[Any]) -> AlertResult:
        """Process assessments and raise or merge alerts.

        forecast: nakabandi.forecast.Forecast (LC-4 shape)
        assessments: list[nakabandi.interception.InterceptAssessment]
        """
        now: SimTime = self._clock.now()
        floor: float = self._policy.alerting.floor_confidence
        escalate_after_min: float = self._policy.alerting.escalate_after_min
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
            if assessment.confidence < floor:
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
                    confidence=assessment.confidence,
                    window_end=window_end,
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
                sev = severity(
                    confidence=assessment.confidence,
                    amount_paise=getattr(forecast, "amount_paise", 0),
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
                    target_kind=assessment.target.kind,
                    target_id=assessment.target.id,
                    target_name=getattr(assessment.target, "name", ""),
                    dedup_key=dk,
                    severity=sev,
                    confidence=assessment.confidence,
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
                    timeline=[init_entry],
                )
                self._repo.save(new_alert)
                raised.append(new_alert)
                alert_ids.append(alert_id)
                if first_alert_id is None:
                    first_alert_id = alert_id
                    first_created = True

        # Budget ranking across all newly raised alerts
        if raised:
            rank_and_cap(raised, self._policy)
            for a in raised:
                self._repo.save(a)
                # Schedule escalation and expiry timers
                escalate_at = a.window_start + timedelta(minutes=escalate_after_min)
                self._escalate_fn(a.id, escalate_at)
                self._expire_fn(a.id, a.expires_at)
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
        )
