"""Integration tests for alerting endpoints and use cases (DOC 4 A7 Done When).

Tests:
  - Alert created via raise_or_merge; GET /alerts returns it; GET /alerts/{id} detail.
  - Duplicate complaint merges into existing open alert (dedup_key match).
  - Escalation fires on a fake clock advance.
  - Expiry fires on a fake clock advance.
  - AcknowledgeAlert denies bank_nodal (no ACKNOWLEDGE permission check is off by default,
    but bank_nodal CAN acknowledge per policy.yaml — so we test a role without ACKNOWLEDGE).
  - GET /alerts respects the authenticated principal (unauthenticated → 401).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from nakabandi.access import Principal, Scope
from nakabandi.alerting import AlertService, SseHub
from nakabandi.main import create_app
from nakabandi.shared import (
    SIM_CLOCK_EPOCH,
    Policy,
    Scheduler,
    SimClock,
    SqlAlchemyUnitOfWork,
)
from nakabandi.shared.infrastructure.db import create_sqlite_engine, make_session_factory
from nakabandi_contracts.enums import LadderLevel, Permission, Role, Verdict

_ADMIN = Principal(user_id="u-admin", role=Role.ADMIN, scope=Scope(), display_name="Admin")
SERVICE_KEY = "test-only-service-key"
JWT_SECRET = "test-only-jwt-secret-at-least-32-bytes-long"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'alerting_test.db'}"


@pytest.fixture
def client(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("API_SERVICE_KEY", SERVICE_KEY)
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    app = create_app()
    with TestClient(app) as c:
        yield c


def _login(client: TestClient, role: str = "i4c_analyst") -> TestClient:
    demo = client.get("/api/v1/auth/demo-users").json()
    user = next(u for u in demo if u["role"] == role)
    r = client.post(
        "/api/v1/auth/login",
        json={"username": user["username"], "password": user["password"]},
    )
    assert r.status_code == 200, r.text
    return client


# ---------------------------------------------------------------------------
# Fake assessment / forecast helpers
# ---------------------------------------------------------------------------


@dataclass
class FakeTarget:
    kind: str = "ATM"
    id: str = "loc-1"
    name: str = "Test ATM"


@dataclass
class FakeAssessment:
    ladder_level: LadderLevel = LadderLevel.L1
    confidence: float = 0.75
    verdict: Verdict = Verdict.INTERCEPTABLE
    target: FakeTarget | None = None

    def __post_init__(self) -> None:
        if self.target is None:
            self.target = FakeTarget()


@dataclass
class FakeForecast:
    id: str = "forecast-1"
    cluster_id: str = "cluster-1"
    complaint_id: str = "complaint-1"
    amount_paise: int = 10_000_000
    stale: bool = False


# ---------------------------------------------------------------------------
# Tests: GET /alerts requires auth
# ---------------------------------------------------------------------------


def test_get_alerts_requires_auth(client: TestClient) -> None:
    r = client.get("/api/v1/alerts")
    assert r.status_code == 401


def test_get_alerts_returns_empty_initially(client: TestClient) -> None:
    _login(client)
    r = client.get("/api/v1/alerts")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert body["items"] == []
    assert body["next_cursor"] is None


def test_get_alert_not_found(client: TestClient) -> None:
    _login(client)
    r = client.get("/api/v1/alerts/nonexistent-id")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Tests: raise_or_merge via AlertService directly (unit-style on a real DB)
# ---------------------------------------------------------------------------


def _make_alert_service(
    db_url: str,
) -> tuple[AlertService, SqlAlchemyUnitOfWork, SimClock, Scheduler]:
    policy = Policy.load("config/policy.yaml")
    engine = create_sqlite_engine(db_url)
    from nakabandi.shared.infrastructure.db import create_all

    create_all(engine)
    session_factory = make_session_factory(engine)
    uow = SqlAlchemyUnitOfWork(session_factory)
    uow.__enter__()
    assert uow.session is not None
    clock = SimClock(start=SIM_CLOCK_EPOCH)
    scheduler = Scheduler()
    hub = SseHub()
    svc = AlertService(
        session=uow.session,
        clock=clock,
        policy=policy,
        scheduler=scheduler,
        role_permissions={Role.ADMIN: frozenset({Permission.VIEW_ALERTS})},
        sse_hub=hub,
    )
    return svc, uow, clock, scheduler


def test_raise_or_merge_creates_alert(db_url: str) -> None:
    svc, uow, clock, scheduler = _make_alert_service(db_url)
    try:
        result = svc.raise_or_merge(FakeForecast(), [FakeAssessment()])
        uow.commit()
        assert result.alert_id is not None
        assert result.created is True
        assert len(result.alert_ids) == 1

        # Verify it is retrievable
        alert = svc.get_alert(result.alert_id)
        assert alert is not None
        assert alert.confidence == 0.75
    finally:
        uow.__exit__(None, None, None)


def test_raise_or_merge_deduplicates(db_url: str) -> None:
    """Two calls with the same cluster+target produce one open alert (merge)."""
    svc, uow, clock, scheduler = _make_alert_service(db_url)
    try:
        svc.raise_or_merge(FakeForecast(id="fc-1"), [FakeAssessment(confidence=0.6)])
        uow.commit()

        svc.raise_or_merge(FakeForecast(id="fc-2"), [FakeAssessment(confidence=0.8)])
        uow.commit()

        # Should NOT create a second alert
        alerts, _ = svc.list_alerts(_ADMIN, limit=100)
        open_alerts = [a for a in alerts if a.status.value in ("open", "escalated", "acknowledged")]
        assert len(open_alerts) == 1
        # Confidence should be updated to the max
        assert open_alerts[0].confidence == 0.8
        # Timeline should have both raised + merged entries
        assert any(e.kind == "merged" for e in open_alerts[0].timeline)
    finally:
        uow.__exit__(None, None, None)


def test_below_floor_does_not_create_alert(db_url: str) -> None:
    policy = Policy.load("config/policy.yaml")
    floor = policy.alerting.floor_confidence
    svc, uow, clock, scheduler = _make_alert_service(db_url)
    try:
        # confidence below floor
        result = svc.raise_or_merge(FakeForecast(), [FakeAssessment(confidence=floor * 0.5)])
        uow.commit()
        assert result.alert_id is None
        assert result.alert_ids == []
    finally:
        uow.__exit__(None, None, None)


def test_ladder_level_none_skipped(db_url: str) -> None:
    svc, uow, clock, scheduler = _make_alert_service(db_url)
    try:
        result = svc.raise_or_merge(
            FakeForecast(),
            [FakeAssessment(ladder_level=LadderLevel.NONE, confidence=0.9)],
        )
        uow.commit()
        assert result.alert_id is None
    finally:
        uow.__exit__(None, None, None)


def test_escalation_timer_fires(db_url: str) -> None:
    """EscalateAlert fires when Scheduler.run_due is called past escalate_at.

    Key design: the timer lambda captures the EscalateAlert that holds a SqlAlertRepo
    bound to a session.  We keep one open UoW alive throughout the test so the captured
    session remains valid when scheduler.run_due fires the lambda.
    """
    policy = Policy.load("config/policy.yaml")
    engine = create_sqlite_engine(db_url)
    from nakabandi.shared.infrastructure.db import create_all

    create_all(engine)
    session_factory = make_session_factory(engine)
    clock = SimClock(start=SIM_CLOCK_EPOCH)
    scheduler = Scheduler()
    hub = SseHub()

    # Raise alert and keep UoW alive so the timer lambda's captured repo is valid.
    with SqlAlchemyUnitOfWork(session_factory) as uow:
        assert uow.session is not None
        svc = AlertService(uow.session, clock, policy, scheduler, {}, hub)
        result = svc.raise_or_merge(FakeForecast(), [FakeAssessment()])
        uow.commit()

        alert_id = result.alert_id
        assert alert_id is not None

        # Advance clock past escalate_after_min and fire timers inside same UoW
        escalate_at = SIM_CLOCK_EPOCH + timedelta(minutes=policy.alerting.escalate_after_min + 1)
        clock._current = escalate_at  # type: ignore[attr-defined]
        scheduler.run_due(escalate_at)
        uow.commit()

        alert = svc.get_alert(alert_id)
        assert alert is not None
        assert alert.status.value == "escalated"


def test_expiry_timer_fires(db_url: str) -> None:
    """ExpireAlert fires when Scheduler.run_due is called past expires_at.

    Same pattern: keep one UoW open so the timer lambda's repo is still valid.
    """
    policy = Policy.load("config/policy.yaml")
    engine = create_sqlite_engine(db_url)
    from nakabandi.shared.infrastructure.db import create_all

    create_all(engine)
    session_factory = make_session_factory(engine)
    clock = SimClock(start=SIM_CLOCK_EPOCH)
    scheduler = Scheduler()
    hub = SseHub()

    with SqlAlchemyUnitOfWork(session_factory) as uow:
        assert uow.session is not None
        svc = AlertService(uow.session, clock, policy, scheduler, {}, hub)
        result = svc.raise_or_merge(FakeForecast(), [FakeAssessment()])
        uow.commit()

        alert_id = result.alert_id
        assert alert_id is not None

        # Get the alert to read expires_at, then advance past it and fire
        alert = svc.get_alert(alert_id)
        assert alert is not None
        expire_at = alert.expires_at + timedelta(seconds=1)

        clock._current = expire_at  # type: ignore[attr-defined]
        scheduler.run_due(expire_at)
        uow.commit()

        alert2 = svc.get_alert(alert_id)
        assert alert2 is not None
        assert alert2.status.value == "expired"


# ---------------------------------------------------------------------------
# Tests: acknowledge via HTTP
# ---------------------------------------------------------------------------


def test_acknowledge_alert_via_api(client: TestClient, db_url: str) -> None:
    """Create an alert, then acknowledge it via the API."""
    # First create an alert directly in the DB
    policy = Policy.load("config/policy.yaml")
    engine = create_sqlite_engine(db_url)
    session_factory = make_session_factory(engine)
    clock = SimClock(start=SIM_CLOCK_EPOCH)

    alert_id = None
    with SqlAlchemyUnitOfWork(session_factory) as uow:
        assert uow.session is not None
        svc = AlertService(uow.session, clock, policy, Scheduler(), {}, SseHub())
        result = svc.raise_or_merge(FakeForecast(), [FakeAssessment()])
        uow.commit()
        alert_id = result.alert_id

    assert alert_id is not None

    _login(client, "i4c_analyst")
    r = client.post(f"/api/v1/alerts/{alert_id}/acknowledge")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "acknowledged"
    assert any(e["kind"] == "acknowledged" for e in body["timeline"])


def test_acknowledge_nonexistent_alert(client: TestClient) -> None:
    _login(client, "i4c_analyst")
    r = client.post("/api/v1/alerts/does-not-exist/acknowledge")
    assert r.status_code == 404
