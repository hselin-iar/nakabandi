"""pipeline.process_complaint — the ONLY module allowed to call several module facades
in sequence (DOC 2 §2.1, DOC 3 LC-3 header, AGENTS.md Agentic Coding Rules).

Invariants enforced here:
  - Only `pipeline` and `main.py` call several facades; no other module imports pipeline.
  - Domain events are published AFTER the synchronous chain, for fan-out only.
  - A failing stage leaves the complaint `unprocessed` with `failed_stage` set; it is
    never lost.
  - Only the application layer (use cases here) owns the unit of work.
"""

from __future__ import annotations

from typing import Any, Protocol

import structlog

from nakabandi.shared import EventBus, ForecastGenerated, Id, SimTime, new_id

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Port protocols (pipeline-local; real modules implement these structurally)
# ---------------------------------------------------------------------------


class _Complaint(Protocol):
    """Minimal complaint shape the pipeline reads."""

    id: Id
    layer1_account_id: Id
    stale: bool  # not on the entity; checked on the forecast not the complaint


class _ComplaintRepo(Protocol):
    """Port: intake.SqlComplaintRepo (subset needed by pipeline)."""

    def get_by_id(self, complaint_id: Id) -> Any | None: ...

    def mark_processed(self, complaint_id: Id) -> None: ...

    def mark_unprocessed(self, complaint_id: Id, *, failed_stage: str) -> None: ...

    def list_unprocessed(self) -> list[Any]: ...


class _ClusterService(Protocol):
    """Port: graph.ClusterService (subset needed by pipeline)."""

    def resolve(self, accounts: list[str], as_of: SimTime) -> Any: ...

    def context_for(self, complaint_id: Id, cluster_id: Id, as_of: SimTime) -> Any: ...


class _Forecaster(Protocol):
    """Port: forecast.Forecaster (subset needed by pipeline)."""

    def generate(self, ctx: Any, as_of: SimTime) -> Any: ...


class _Interceptor(Protocol):
    """Port: interception.Interceptor (subset needed by pipeline)."""

    def assess(self, forecast: Any, complaint_id: Id, now: SimTime) -> list[Any]: ...


class _AlertService(Protocol):
    """Port: alerting.AlertService (subset needed by pipeline)."""

    def raise_or_merge(self, forecast: Any, assessments: list[Any]) -> Any: ...


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class ProcessResult:
    """Outcome of ProcessComplaint.run()."""

    __slots__ = ("complaint_id", "ok", "failed_stage", "alert_id")

    def __init__(
        self,
        complaint_id: Id,
        *,
        ok: bool,
        failed_stage: str | None = None,
        alert_id: Id | None = None,
    ) -> None:
        self.complaint_id = complaint_id
        self.ok = ok
        self.failed_stage = failed_stage
        self.alert_id = alert_id

    def __repr__(self) -> str:
        if self.ok:
            return f"ProcessResult(ok=True, alert_id={self.alert_id!r})"
        return f"ProcessResult(ok=False, failed_stage={self.failed_stage!r})"


# ---------------------------------------------------------------------------
# ProcessComplaint
# ---------------------------------------------------------------------------


class ProcessComplaint:
    """Run the synchronous complaint chain (DOC 3 M2):

        graph.resolve → graph.context_for → forecast.generate →
        interception.assess → alerting.raise_or_merge

    Each stage that fails marks the complaint `unprocessed` with its stage name
    and returns immediately.  On success, marks it `processed`.

    The caller (main.py / RetryUnprocessed) owns the unit of work; this use case
    does NOT commit — it calls flush only inside the repo methods.
    """

    def __init__(
        self,
        complaint_repo: _ComplaintRepo,
        cluster_service: _ClusterService,
        forecaster: _Forecaster,
        interceptor: _Interceptor,
        alert_service: _AlertService,
        bus: EventBus | None = None,
    ) -> None:
        self._bus = bus
        self._complaints = complaint_repo
        self._cluster = cluster_service
        self._forecast = forecaster
        self._intercept = interceptor
        self._alerts = alert_service

    def run(self, complaint_id: Id, now: SimTime) -> ProcessResult:
        log = logger.bind(complaint_id=complaint_id)

        # ------------------------------------------------------------------
        # Load the complaint
        # ------------------------------------------------------------------
        complaint = self._complaints.get_by_id(complaint_id)
        if complaint is None:
            log.error("pipeline.complaint_not_found")
            return ProcessResult(complaint_id, ok=False, failed_stage="load")

        # ------------------------------------------------------------------
        # Stage 1: graph.resolve
        # ------------------------------------------------------------------
        try:
            resolution = self._cluster.resolve([complaint.layer1_account_id], now)
            cluster_id = resolution.cluster_id
        except Exception:
            log.exception("pipeline.stage.graph_resolve.failed")
            self._complaints.mark_unprocessed(complaint_id, failed_stage="graph.resolve")
            return ProcessResult(complaint_id, ok=False, failed_stage="graph.resolve")

        # ------------------------------------------------------------------
        # Stage 2: graph.context_for
        # ------------------------------------------------------------------
        try:
            ctx = self._cluster.context_for(complaint_id, cluster_id, now)
        except Exception:
            log.exception("pipeline.stage.graph_context.failed")
            self._complaints.mark_unprocessed(complaint_id, failed_stage="graph.context_for")
            return ProcessResult(complaint_id, ok=False, failed_stage="graph.context_for")

        # ------------------------------------------------------------------
        # Stage 3: forecast.generate
        # ------------------------------------------------------------------
        try:
            forecast = self._forecast.generate(ctx, now)
        except Exception:
            log.exception("pipeline.stage.forecast.failed")
            self._complaints.mark_unprocessed(complaint_id, failed_stage="forecast.generate")
            return ProcessResult(complaint_id, ok=False, failed_stage="forecast.generate")

        # Stale forecast → skip alert creation; store as processed (not an error)
        if forecast.stale:
            log.info("pipeline.forecast.stale", complaint_id=complaint_id)
            self._complaints.mark_processed(complaint_id)
            self._publish_forecast(forecast, complaint_id, now)
            return ProcessResult(complaint_id, ok=True, alert_id=None)

        # ------------------------------------------------------------------
        # Stage 4: interception.assess
        # ------------------------------------------------------------------
        try:
            assessments = self._intercept.assess(forecast, complaint_id, now)
        except Exception:
            log.exception("pipeline.stage.interception.failed")
            self._complaints.mark_unprocessed(complaint_id, failed_stage="interception.assess")
            return ProcessResult(complaint_id, ok=False, failed_stage="interception.assess")

        # ------------------------------------------------------------------
        # Stage 5: alerting.raise_or_merge
        # ------------------------------------------------------------------
        try:
            alert_result = self._alerts.raise_or_merge(forecast, assessments)
        except Exception:
            log.exception("pipeline.stage.alerting.failed")
            self._complaints.mark_unprocessed(complaint_id, failed_stage="alerting.raise_or_merge")
            return ProcessResult(complaint_id, ok=False, failed_stage="alerting.raise_or_merge")

        # ------------------------------------------------------------------
        # All stages succeeded
        # ------------------------------------------------------------------
        self._complaints.mark_processed(complaint_id)
        self._publish_forecast(forecast, complaint_id, now)
        log.info(
            "pipeline.complaint.processed",
            alert_id=getattr(alert_result, "alert_id", None),
        )
        return ProcessResult(
            complaint_id,
            ok=True,
            alert_id=getattr(alert_result, "alert_id", None),
        )

    def _publish_forecast(self, forecast: Any, complaint_id: Id, now: SimTime) -> None:
        """LC-3 fan-out, after the chain: the analytics projector listens. A failing subscriber is
        logged and never makes a processed complaint look unprocessed."""
        if self._bus is None:
            return
        try:
            self._bus.publish(
                ForecastGenerated(
                    event_id=new_id(),
                    occurred_at=now,
                    forecast_id=forecast.id,
                    complaint_id=complaint_id,
                )
            )
        except Exception:
            logger.exception(
                "pipeline.forecast_generated.publish_failed", complaint_id=complaint_id
            )


# ---------------------------------------------------------------------------
# RetryUnprocessed
# ---------------------------------------------------------------------------


class RetryUnprocessed:
    """Re-run ProcessComplaint on every complaint with processing_status='unprocessed'.

    Called at boot and every 5 minutes by the Scheduler (DOC 3 M2).
    """

    def __init__(self, complaint_repo: _ComplaintRepo, process_complaint: ProcessComplaint) -> None:
        self._complaints = complaint_repo
        self._process = process_complaint

    def run(self, now: SimTime) -> list[ProcessResult]:
        unprocessed = self._complaints.list_unprocessed()
        results: list[ProcessResult] = []
        for complaint in unprocessed:
            result = self._process.run(complaint.id, now)
            results.append(result)
            logger.info(
                "pipeline.retry.result",
                complaint_id=complaint.id,
                ok=result.ok,
                failed_stage=result.failed_stage,
            )
        return results


# ---------------------------------------------------------------------------
# RefreshOpenAlerts
# ---------------------------------------------------------------------------


class RefreshOpenAlerts:
    """Re-run the forecast and interception chain for complaints behind open alerts.

    New hops or observations that arrived since the alert was raised may change
    the picture.  Called by the Scheduler every policy.alerting.refresh_min sim-minutes
    (DOC 3 M2).

    NOTE: In this v0, RefreshOpenAlerts is a no-op placeholder — alerting.AlertService
    is not yet built.  The Scheduler wires the real implementation at Sync 3 (A7).
    """

    def run(self, now: SimTime) -> None:
        logger.debug("pipeline.refresh_open_alerts.noop", now=now.isoformat())
