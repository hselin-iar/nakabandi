"""SqlAlertRepo and SqlOutcomeRepo — SQLAlchemy implementations of alerting ports."""

from __future__ import annotations

from datetime import UTC, datetime

from nakabandi_contracts.enums import ActionType, AlertStatus
from sqlalchemy.orm import Session

from nakabandi.alerting.domain.action import Action, ActionStatus
from nakabandi.alerting.domain.alert import Alert, TimelineEntry
from nakabandi.alerting.domain.delivery import (
    Delivery,
    DeliveryChannel,
    DeliveryStatus,
    WebhookKind,
)
from nakabandi.alerting.domain.outcome import Outcome
from nakabandi.alerting.infrastructure.models import (
    ActionModel,
    AlertModel,
    AlertTimelineModel,
    DeliveryModel,
    OutcomeModel,
)
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
        complaint_id=row.complaint_id,
        masked=row.masked,
        priority=row.priority,
        budget_rank=row.budget_rank,
        scope_state_id=row.scope_state_id,
        scope_district_id=row.scope_district_id,
        scope_bank_id=row.scope_bank_id,
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
        complaint_id=alert.complaint_id,
        masked=alert.masked,
        priority=alert.priority,
        budget_rank=alert.budget_rank,
        scope_state_id=alert.scope_state_id,
        scope_district_id=alert.scope_district_id,
        scope_bank_id=alert.scope_bank_id,
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
        view: str = "all",
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Alert], str | None]:
        """Paginated listing. Cursor is the last seen created_at ISO string. `view` is the
        budget view: "queue" (not deferred), "backlog" (deferred only) or "all"."""
        q = self._session.query(AlertModel)
        if status is not None:
            q = q.filter(AlertModel.status == status)
        if view == "queue":
            q = q.filter(AlertModel.is_deferred.is_(False))
        elif view == "backlog":
            q = q.filter(AlertModel.is_deferred.is_(True))
        # Same precedence as access.authorize's scope check: bank, then district, then state.
        if bank_id is not None:
            q = q.filter(AlertModel.scope_bank_id == bank_id)
        elif district_id is not None:
            q = q.filter(AlertModel.scope_district_id == district_id)
        elif state_id is not None:
            q = q.filter(AlertModel.scope_state_id == state_id)
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

    def _load(self, rows: list[AlertModel]) -> list[Alert]:
        out = []
        for row in rows:
            tl = self._session.query(AlertTimelineModel).filter_by(alert_id=row.id).all()
            out.append(_model_to_alert(row, tl))
        return out

    def list_queue(self, district_id: str | None, start: datetime, end: datetime) -> list[Alert]:
        """Every alert of one budget queue: its district (None = unscoped), created in one shift
        [start, end)."""
        q = self._session.query(AlertModel).filter(
            AlertModel.created_at >= start, AlertModel.created_at < end
        )
        q = q.filter(
            AlertModel.scope_district_id.is_(None)
            if district_id is None
            else AlertModel.scope_district_id == district_id
        )
        return self._load(q.all())

    def list_awaiting_outcome(self, target_id: str | None = None) -> list[Alert]:
        """Alerts of any status that ReconcileOutcome has not yet decided (no reconciled outcome
        row), optionally only those targeting one location."""
        decided = self._session.query(OutcomeModel.alert_id).filter(
            OutcomeModel.source == "reconciled"
        )
        q = self._session.query(AlertModel).filter(AlertModel.id.not_in(decided))
        if target_id is not None:
            q = q.filter(AlertModel.target_id == target_id)
        return self._load(q.all())

    def list_for_review(
        self,
        *,
        state_id: str | None = None,
        district_id: str | None = None,
        bank_id: str | None = None,
        limit: int = 1000,
    ) -> list[Alert]:
        """Alerts no officer has labelled yet, inside the scope filter (the review queue's
        candidates; ordering is the domain's job)."""
        labelled = self._session.query(OutcomeModel.alert_id).filter(
            OutcomeModel.source == "officer"
        )
        q = self._session.query(AlertModel).filter(AlertModel.id.not_in(labelled))
        if bank_id is not None:
            q = q.filter(AlertModel.scope_bank_id == bank_id)
        elif district_id is not None:
            q = q.filter(AlertModel.scope_district_id == district_id)
        elif state_id is not None:
            q = q.filter(AlertModel.scope_state_id == state_id)
        return self._load(q.order_by(AlertModel.created_at.desc()).limit(limit).all())

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
            existing.priority = alert.priority
            existing.budget_rank = alert.budget_rank

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


def _outcome_from_row(row: OutcomeModel) -> Outcome:
    return Outcome(
        id=row.id,
        alert_id=row.alert_id,
        result=row.result,
        observation_id=row.observation_id,
        decided_at=to_sim_time(row.decided_at),
        source=row.source,
        actor_id=row.actor_id,
        location_id=row.location_id,
        reason=row.reason,
    )


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
                source=outcome.source,
                actor_id=outcome.actor_id,
                location_id=outcome.location_id,
                reason=outcome.reason,
            )
        )
        self._session.flush()

    def list_for_alert(self, alert_id: str) -> list[Outcome]:
        rows = (
            self._session.query(OutcomeModel)
            .filter_by(alert_id=alert_id)
            .order_by(OutcomeModel.decided_at)
        )
        return [_outcome_from_row(r) for r in rows]

    def find_officer(self, alert_id: str, result: str, location_id: str | None) -> Outcome | None:
        """The officer outcome already recorded for (alert, result, location), if any."""
        row = (
            self._session.query(OutcomeModel)
            .filter_by(alert_id=alert_id, source="officer", result=result, location_id=location_id)
            .first()
        )
        return _outcome_from_row(row) if row is not None else None


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


def _action_from_row(row: ActionModel) -> Action:
    return Action(
        id=row.id,
        alert_id=row.alert_id,
        type=ActionType(row.type),
        actor_user_id=row.actor_user_id,
        actor_role=row.actor_role,
        reason=row.reason,
        params=row.params or {},
        status=ActionStatus(row.status),
        at=to_sim_time(row.at),
        status_at=to_sim_time(row.status_at),
        note=row.note,
        applied_amount_paise=row.applied_amount_paise,
    )


class SqlActionRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, action_id: str) -> Action | None:
        row = self._session.get(ActionModel, action_id)
        return _action_from_row(row) if row is not None else None

    def list_for_alert(self, alert_id: str) -> list[Action]:
        rows = (
            self._session.query(ActionModel).filter_by(alert_id=alert_id).order_by(ActionModel.at)
        )
        return [_action_from_row(r) for r in rows]

    def active_hold_total_for_complaint(self, complaint_id: str) -> int:
        """Sum of proposed_paise over this complaint's hold requests that still count against
        the disputed total: everything except a hold the bank rejected or later released."""
        rows = self._session.query(ActionModel).filter(
            ActionModel.type == ActionType.REQUEST_HOLD.value,
            ActionModel.status.in_([ActionStatus.PENDING.value, ActionStatus.APPLIED.value]),
        )
        return sum(
            int(r.params.get("proposed_paise", 0))
            for r in rows
            if (r.params or {}).get("complaint_id") == complaint_id
        )

    def active_hold_totals_by_account(self, complaint_id: str) -> dict[str, int]:
        """Paise already proposed for hold, per account, for one complaint (pending + applied)."""
        rows = self._session.query(ActionModel).filter(
            ActionModel.type == ActionType.REQUEST_HOLD.value,
            ActionModel.status.in_([ActionStatus.PENDING.value, ActionStatus.APPLIED.value]),
        )
        totals: dict[str, int] = {}
        for r in rows:
            params = r.params or {}
            if params.get("complaint_id") == complaint_id and params.get("account_id"):
                account = str(params["account_id"])
                totals[account] = totals.get(account, 0) + int(params.get("proposed_paise", 0))
        return totals

    def list_active_holds(self) -> list[Action]:
        """Hold requests the bank has not rejected or released: their lien-review timer is live."""
        rows = self._session.query(ActionModel).filter(
            ActionModel.type == ActionType.REQUEST_HOLD.value,
            ActionModel.status.in_([ActionStatus.PENDING.value, ActionStatus.APPLIED.value]),
        )
        return [_action_from_row(r) for r in rows]

    def add(self, action: Action) -> None:
        self._session.add(
            ActionModel(
                id=action.id,
                alert_id=action.alert_id,
                type=action.type.value,
                actor_user_id=action.actor_user_id,
                actor_role=action.actor_role,
                reason=action.reason,
                params=action.params,
                status=action.status.value,
                at=action.at,
                status_at=action.status_at,
                note=action.note,
                applied_amount_paise=action.applied_amount_paise,
            )
        )
        self._session.flush()

    def save(self, action: Action) -> None:
        row = self._session.get(ActionModel, action.id)
        assert row is not None, "save() is for an existing action; use add() for a new one"
        row.status = action.status.value
        row.status_at = action.status_at
        row.note = action.note
        row.applied_amount_paise = action.applied_amount_paise
        self._session.flush()


# ---------------------------------------------------------------------------
# Deliveries (the outbox)
# ---------------------------------------------------------------------------


def _delivery_from_row(row: DeliveryModel) -> Delivery:
    return Delivery(
        id=row.id,
        alert_id=row.alert_id,
        action_id=row.action_id,
        channel=DeliveryChannel(row.channel),
        webhook_kind=WebhookKind(row.webhook_kind) if row.webhook_kind else None,
        recipient=row.recipient,
        rendered_body=row.rendered_body,
        payload=row.payload or {},
        idempotency_key=row.idempotency_key,
        status=DeliveryStatus(row.status),
        attempts=row.attempts,
        next_attempt_at=row.next_attempt_at,
        created_at=row.created_at,
        provider=row.provider,
        last_error=row.last_error,
        sent_at=row.sent_at,
    )


class SqlDeliveryRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, delivery: Delivery) -> None:
        self._session.add(
            DeliveryModel(
                id=delivery.id,
                alert_id=delivery.alert_id,
                action_id=delivery.action_id,
                channel=delivery.channel.value,
                provider=delivery.provider,
                webhook_kind=delivery.webhook_kind.value if delivery.webhook_kind else None,
                recipient=delivery.recipient,
                rendered_body=delivery.rendered_body,
                payload=delivery.payload,
                idempotency_key=delivery.idempotency_key,
                status=delivery.status.value,
                attempts=delivery.attempts,
                next_attempt_at=delivery.next_attempt_at,
                created_at=delivery.created_at,
                last_error=delivery.last_error,
                sent_at=delivery.sent_at,
            )
        )
        self._session.flush()

    def save(self, delivery: Delivery) -> None:
        row = self._session.get(DeliveryModel, delivery.id)
        assert row is not None, "save() is for an existing delivery; use add() for a new one"
        row.status = delivery.status.value
        row.attempts = delivery.attempts
        row.next_attempt_at = delivery.next_attempt_at
        row.last_error = delivery.last_error
        row.sent_at = delivery.sent_at
        row.provider = delivery.provider
        self._session.flush()

    def get_by_id(self, delivery_id: str) -> Delivery | None:
        row = self._session.get(DeliveryModel, delivery_id)
        return _delivery_from_row(row) if row is not None else None

    def list_due(self, now_wall: datetime, limit: int = 50) -> list[Delivery]:
        rows = (
            self._session.query(DeliveryModel)
            .filter(
                DeliveryModel.status.in_(
                    [DeliveryStatus.PENDING.value, DeliveryStatus.FAILED.value]
                ),
                DeliveryModel.next_attempt_at <= now_wall,
            )
            .order_by(DeliveryModel.next_attempt_at)
            .limit(limit)
        )
        return [_delivery_from_row(r) for r in rows]

    def list_for_alert(self, alert_id: str) -> list[Delivery]:
        rows = (
            self._session.query(DeliveryModel)
            .filter_by(alert_id=alert_id)
            .order_by(DeliveryModel.created_at)
        )
        return [_delivery_from_row(r) for r in rows]

    def list_page(
        self,
        *,
        status: str | None = None,
        channel: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
        state_id: str | None = None,
        district_id: str | None = None,
        bank_id: str | None = None,
    ) -> tuple[list[Delivery], str | None]:
        """Newest first, restricted to the alerts a principal's scope can see (same precedence
        as SqlAlertRepo.list_by_scope). The cursor is the last seen created_at ISO string."""
        q = self._session.query(DeliveryModel)
        visible = self._session.query(AlertModel.id)
        if bank_id is not None:
            visible = visible.filter(AlertModel.scope_bank_id == bank_id)
        elif district_id is not None:
            visible = visible.filter(AlertModel.scope_district_id == district_id)
        elif state_id is not None:
            visible = visible.filter(AlertModel.scope_state_id == state_id)
        else:
            visible = None
        if visible is not None:
            q = q.filter(DeliveryModel.alert_id.in_(visible))
        if status is not None:
            q = q.filter(DeliveryModel.status == status)
        if channel is not None:
            q = q.filter(DeliveryModel.channel == channel)
        if cursor is not None:
            try:
                q = q.filter(
                    DeliveryModel.created_at < datetime.fromisoformat(cursor).replace(tzinfo=UTC)
                )
            except ValueError:
                pass
        rows = q.order_by(DeliveryModel.created_at.desc()).limit(limit + 1).all()
        has_more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = rows[-1].created_at.isoformat() if has_more and rows else None
        return [_delivery_from_row(r) for r in rows], next_cursor

    def count_dead(self) -> int:
        return (
            self._session.query(DeliveryModel).filter_by(status=DeliveryStatus.DEAD.value).count()
        )
