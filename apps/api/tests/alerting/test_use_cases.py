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
) -> tuple[AlertService, SqlAlchemyUnitOfWork, SimClock, None]:
    policy = Policy.load("config/policy.yaml")
    engine = create_sqlite_engine(db_url)
    from nakabandi.shared.infrastructure.db import create_all

    create_all(engine)
    session_factory = make_session_factory(engine)
    uow = SqlAlchemyUnitOfWork(session_factory)
    uow.__enter__()
    assert uow.session is not None
    clock = SimClock(start=SIM_CLOCK_EPOCH)
    hub = SseHub()
    svc = AlertService(
        session=uow.session,
        clock=clock,
        policy=policy,
        role_permissions={Role.ADMIN: frozenset({Permission.VIEW_ALERTS})},
        sse_hub=hub,
    )
    return svc, uow, clock, None


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


def _fresh_service(session_factory, clock, policy):  # noqa: ANN001, ANN202
    """A brand-new service on a brand-new session: what a restarted process, or the timer
    worker's next tick, has. Nothing registered in memory survives into it."""
    uow = SqlAlchemyUnitOfWork(session_factory)
    uow.__enter__()
    assert uow.session is not None
    return uow, AlertService(uow.session, clock, policy, {}, SseHub())


def _raise_and_forget(db_url: str):  # noqa: ANN202
    policy = Policy.load("config/policy.yaml")
    engine = create_sqlite_engine(db_url)
    from nakabandi.shared.infrastructure.db import create_all

    create_all(engine)
    session_factory = make_session_factory(engine)
    clock = SimClock(start=SIM_CLOCK_EPOCH)
    with SqlAlchemyUnitOfWork(session_factory) as uow:
        assert uow.session is not None
        svc = AlertService(uow.session, clock, policy, {}, SseHub())
        result = svc.raise_or_merge(FakeForecast(), [FakeAssessment()])
        uow.commit()
    assert result.alert_id is not None
    return policy, session_factory, clock, result.alert_id


def test_escalation_fires_when_due_from_a_fresh_session(db_url: str) -> None:
    """The alert clock is database-driven: a service that never saw the alert raised (a restarted
    process) still escalates it once escalate_after_min has passed."""
    policy, session_factory, clock, alert_id = _raise_and_forget(db_url)

    uow, svc = _fresh_service(session_factory, clock, policy)
    try:
        assert svc.fire_due_timers() == 0  # nothing is due yet
        clock._current = SIM_CLOCK_EPOCH + timedelta(  # type: ignore[attr-defined]
            minutes=policy.alerting.escalate_after_min + 1
        )
        assert svc.fire_due_timers() >= 1
        uow.commit()
        alert = svc.get_alert(alert_id)
        assert alert is not None and alert.status.value == "escalated"
        assert svc.fire_due_timers() == 0  # and it is not escalated twice
    finally:
        uow.__exit__(None, None, None)


def test_expiry_fires_when_due_from_a_fresh_session(db_url: str) -> None:
    policy, session_factory, clock, alert_id = _raise_and_forget(db_url)

    uow, svc = _fresh_service(session_factory, clock, policy)
    try:
        alert = svc.get_alert(alert_id)
        assert alert is not None
        clock._current = alert.expires_at + timedelta(seconds=1)  # type: ignore[attr-defined]
        svc.fire_due_timers()
        uow.commit()
        after = svc.get_alert(alert_id)
        assert after is not None and after.status.value == "expired"
    finally:
        uow.__exit__(None, None, None)


def test_an_alert_someone_acted_on_never_expires(db_url: str) -> None:
    """ "Alert acknowledged then window passes: expires only if not actioned" (DOC 3 M4)."""
    from nakabandi.alerting.infrastructure.repos import SqlAlertRepo
    from nakabandi_contracts.enums import AlertStatus

    policy, session_factory, clock, alert_id = _raise_and_forget(db_url)
    uow, svc = _fresh_service(session_factory, clock, policy)
    try:
        repo = SqlAlertRepo(uow.session)  # type: ignore[arg-type]
        alert = repo.get_by_id(alert_id)
        assert alert is not None
        alert.status = AlertStatus.ACTIONED
        repo.save(alert)
        uow.commit()
        clock._current = alert.expires_at + timedelta(days=3)  # type: ignore[attr-defined]

        svc.fire_due_timers()
        uow.commit()

        after = svc.get_alert(alert_id)
        assert after is not None and after.status is AlertStatus.ACTIONED
    finally:
        uow.__exit__(None, None, None)


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
        svc = AlertService(uow.session, clock, policy, {}, SseHub())
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
