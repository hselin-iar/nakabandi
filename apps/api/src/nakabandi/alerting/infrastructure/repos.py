"""SqlAlertRepo and SqlOutcomeRepo — SQLAlchemy implementations of alerting ports."""

from __future__ import annotations

from datetime import UTC

from nakabandi_contracts.enums import AlertStatus
from sqlalchemy.orm import Session

from nakabandi.alerting.domain.alert import Alert, TimelineEntry
from nakabandi.alerting.domain.outcome import Outcome
from nakabandi.alerting.infrastructure.models import AlertModel, AlertTimelineModel, OutcomeModel
from nakabandi.shared import to_sim_time


def _model_to_alert(row: AlertModel, timeline_rows: list[AlertTimelineModel]) -> Alert:
    timeline = [
        TimelineEntry(
            id=t.id,
            alert_id=t.alert_id,
            at=to_sim_time(t.at),
            kind=t.kind,
            actor_id=t.actor_id,
            text_code=t.text_code,
            text_params=t.text_params or {},
        )
        for t in sorted(timeline_rows, key=lambda x: x.at)
    ]
    from nakabandi_contracts.enums import LadderLevel, Severity

    return Alert(
        id=row.id,
        cluster_ref=row.cluster_ref,
        target_kind=row.target_kind,
        target_id=row.target_id,
        target_name=row.target_name,
        dedup_key=row.dedup_key,
        severity=Severity(row.severity),
        confidence=row.confidence,
        status=AlertStatus(row.status),
        ladder_level=LadderLevel(row.ladder_level),
        is_deferred=row.is_deferred,
        is_probe=row.is_probe,
        window_start=to_sim_time(row.window_start),
        window_end=to_sim_time(row.window_end),
        expires_at=to_sim_time(row.expires_at),
        created_at=to_sim_time(row.created_at),
        forecast_id=row.forecast_id,
        masked=row.masked,
        timeline=timeline,
    )


def _alert_to_model(alert: Alert) -> AlertModel:
    return AlertModel(
        id=alert.id,
        cluster_ref=alert.cluster_ref,
        target_kind=alert.target_kind,
        target_id=alert.target_id,
        target_name=alert.target_name,
        dedup_key=alert.dedup_key,
        severity=alert.severity.value,
        confidence=alert.confidence,
        status=alert.status.value,
        ladder_level=alert.ladder_level.value,
        is_deferred=alert.is_deferred,
        is_probe=alert.is_probe,
        window_start=alert.window_start,
        window_end=alert.window_end,
        expires_at=alert.expires_at,
        created_at=alert.created_at,
        forecast_id=alert.forecast_id,
        masked=alert.masked,
    )


class SqlAlertRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, alert_id: str) -> Alert | None:
        row = self._session.get(AlertModel, alert_id)
        if row is None:
            return None
        tl = self._session.query(AlertTimelineModel).filter_by(alert_id=alert_id).all()
        return _model_to_alert(row, tl)

    def get_by_dedup_key(self, dedup_key: str) -> Alert | None:
        """Return the most-recent open (or escalated/acknowledged) alert for this key."""
        row = (
            self._session.query(AlertModel)
            .filter(
                AlertModel.dedup_key == dedup_key,
                AlertModel.status.in_(
                    [
                        AlertStatus.OPEN.value,
                        AlertStatus.ESCALATED.value,
                        AlertStatus.ACKNOWLEDGED.value,
                    ]
                ),
            )
            .order_by(AlertModel.created_at.desc())
            .first()
        )
        if row is None:
            return None
        tl = self._session.query(AlertTimelineModel).filter_by(alert_id=row.id).all()
        return _model_to_alert(row, tl)

    def list_open(self) -> list[Alert]:
        """All non-terminal alerts (OPEN + ESCALATED + ACKNOWLEDGED)."""
        rows = (
            self._session.query(AlertModel)
            .filter(
                AlertModel.status.in_(
                    [
                        AlertStatus.OPEN.value,
                        AlertStatus.ESCALATED.value,
                        AlertStatus.ACKNOWLEDGED.value,
                    ]
                )
            )
            .all()
        )
        result = []
        for row in rows:
            tl = self._session.query(AlertTimelineModel).filter_by(alert_id=row.id).all()
            result.append(_model_to_alert(row, tl))
        return result

    def list_by_scope(
        self,
        *,
        state_id: str | None = None,
        district_id: str | None = None,
        bank_id: str | None = None,
        status: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Alert], str | None]:
        """Paginated listing. Cursor is the last seen created_at ISO string."""
        q = self._session.query(AlertModel)
        if status is not None:
            q = q.filter(AlertModel.status == status)
        # Scope filtering: bank_id on alerts not yet available in A7
        # (target_id is a location, not a bank). Full scope lands at Sync 4.
        if cursor is not None:
            from datetime import datetime

            try:
                cur_dt = datetime.fromisoformat(cursor).replace(tzinfo=UTC)
                q = q.filter(AlertModel.created_at < cur_dt)
            except ValueError:
                pass
        q = q.order_by(AlertModel.created_at.desc()).limit(limit + 1)
        rows = q.all()

        has_more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = rows[-1].created_at.isoformat() if has_more and rows else None

        alerts = []
        for row in rows:
            tl = self._session.query(AlertTimelineModel).filter_by(alert_id=row.id).all()
            alerts.append(_model_to_alert(row, tl))
        return alerts, next_cursor

    def save(self, alert: Alert) -> None:
        """Upsert alert + any new timeline entries."""
        existing = self._session.get(AlertModel, alert.id)
        if existing is None:
            self._session.add(_alert_to_model(alert))
        else:
            existing.severity = alert.severity.value
            existing.confidence = alert.confidence
            existing.status = alert.status.value
            existing.is_deferred = alert.is_deferred
            existing.is_probe = alert.is_probe
            existing.window_end = alert.window_end
            existing.expires_at = alert.expires_at
            existing.forecast_id = alert.forecast_id
            existing.masked = alert.masked

        # Persist any new timeline entries
        existing_ids: set[str] = {
            row.id
            for row in self._session.query(AlertTimelineModel.id).filter_by(alert_id=alert.id).all()
        }
        for entry in alert.timeline:
            if entry.id not in existing_ids:
                self._session.add(
                    AlertTimelineModel(
                        id=entry.id,
                        alert_id=entry.alert_id,
                        at=entry.at,
                        kind=entry.kind,
                        actor_id=entry.actor_id,
                        text_code=entry.text_code,
                        text_params=entry.text_params,
                    )
                )
        self._session.flush()


class SqlOutcomeRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, outcome: Outcome) -> None:
        self._session.add(
            OutcomeModel(
                id=outcome.id,
                alert_id=outcome.alert_id,
                result=outcome.result,
                observation_id=outcome.observation_id,
                decided_at=outcome.decided_at,
            )
        )
        self._session.flush()
