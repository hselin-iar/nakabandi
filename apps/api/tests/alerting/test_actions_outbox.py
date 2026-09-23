"""A8 Done When (DOC 4 Step A8): request_hold by an investigator creates an Action, an audit
entry and a hold_request delivery; a bank_nodal principal is denied; a failing channel retries
with backoff then dead-letters and shows in the outbox view; the callback updates the action
status; signature verification passes against a bank-shaped receiver.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from nakabandi.alerting import AlertService, DeliveryChannel
from nakabandi.alerting.domain.delivery import (
    Delivery,
    DeliveryStatus,
    WebhookKind,
    backoff_seconds,
)
from nakabandi.alerting.domain.messages import DeliveryResult
from nakabandi.alerting.domain.signing import sign, verify, within_window
from nakabandi.alerting.infrastructure.channels.webhook_bank import BankWebhook
from nakabandi.alerting.infrastructure.models import ActionModel, DeliveryModel
from nakabandi.audit.infrastructure.models import AuditEntryModel
from nakabandi.intake.infrastructure.models import AccountModel
from nakabandi.main import create_app
from nakabandi.shared import SqlAlchemyUnitOfWork, SystemClock
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from alerting.test_use_cases import FakeAssessment, FakeForecast

SERVICE_KEY = "test-only-service-key"
SERVICE_HEADERS = {"X-Nakabandi-Service-Key": SERVICE_KEY}
FIXTURE = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "mini_ingest.json").read_text()
)
SECRET = "test-webhook-secret"
T0 = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("API_SERVICE_KEY", SERVICE_KEY)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'a8.db'}")
    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-at-least-32-bytes-long")
    monkeypatch.setenv("WEBHOOK_SECRET", SECRET)
    with TestClient(create_app()) as c:
        for path, key in (
            ("registry", "registry"),
            ("complaints", "complaints"),
            ("hops", "hops"),
        ):
            r = c.post(f"/api/v1/ingest/{path}", json=FIXTURE[key], headers=SERVICE_HEADERS)
            assert r.status_code == 200, r.text
        yield c


def _login(client: TestClient, role: str) -> None:
    users = client.get("/api/v1/auth/demo-users").json()
    user = next(u for u in users if u["role"] == role)
    r = client.post(
        "/api/v1/auth/login", json={"username": user["username"], "password": user["password"]}
    )
    assert r.status_code == 200, r.text


def _uow(client: TestClient) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(client.app.state.session_factory)  # type: ignore[attr-defined]


def _service(client: TestClient, session) -> AlertService:  # noqa: ANN001
    st = client.app.state  # type: ignore[attr-defined]
    return AlertService(
        session=session,
        clock=st.clock,
        policy=st.policy,
        scheduler=st.scheduler,
        role_permissions=st.role_permissions,
        sse_hub=st.sse_hub,
    )


def _new_alert(client: TestClient, target_id: str = "loc-1") -> str:
    from alerting.test_use_cases import FakeTarget

    with _uow(client) as uow:
        assert uow.session is not None
        result = _service(client, uow.session).raise_or_merge(
            FakeForecast(), [FakeAssessment(target=FakeTarget(id=target_id))]
        )
        uow.commit()
    assert result.alert_id is not None
    return result.alert_id


def _account_id(client: TestClient, account_ref: str) -> str:
    with _uow(client) as uow:
        assert uow.session is not None
        return uow.session.scalars(
            select(AccountModel.id).where(AccountModel.account_ref == account_ref)
        ).one()


def _rows(client: TestClient, model):  # noqa: ANN001, ANN202
    with _uow(client) as uow:
        assert uow.session is not None
        rows = list(uow.session.scalars(select(model)))
        uow.session.expunge_all()
        return rows


def _hold(client: TestClient, alert_id: str, account_ref: str, paise: int):  # noqa: ANN202
    return client.post(
        f"/api/v1/alerts/{alert_id}/actions",
        json={
            "type": "request_hold",
            "reason": "pattern matches complaint c1",
            "params": {"account_id": _account_id(client, account_ref), "proposed_paise": paise},
        },
    )


# ---------------------------------------------------------------------------
# request_hold: Action + audit entry + hold_request delivery
# ---------------------------------------------------------------------------


def test_investigator_request_hold_creates_action_audit_and_delivery(client: TestClient) -> None:
    alert_id = _new_alert(client)
    _login(client, "state_investigator")

    r = _hold(client, alert_id, "ACC-5", 400_000)  # c1 traced 480_000 into acc-5

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["type"] == "request_hold" and body["status"] == "pending"
    assert body["actor_role"] == "state_investigator"

    actions = _rows(client, ActionModel)
    assert [a.id for a in actions] == [body["id"]]

    audit = [a for a in _rows(client, AuditEntryModel) if a.action == "action.recorded"]
    assert len(audit) == 1 and audit[0].entity_id == alert_id
    assert audit[0].payload["action_id"] == body["id"]

    deliveries = _rows(client, DeliveryModel)
    assert len(deliveries) == 1
    d = deliveries[0]
    assert (d.channel, d.webhook_kind, d.action_id) == ("webhook", "hold_request", body["id"])
    assert d.payload["request_id"] == body["id"]  # LC-6: request_id is the action id
    assert d.payload["proposed_lien_paise"] == 400_000
    assert d.payload["disputed_amount_paise"] == 480_000
    assert d.payload["requested_by_role"] == "state_investigator"

    detail = client.get(f"/api/v1/alerts/{alert_id}").json()
    assert detail["status"] == "actioned"


def test_rendered_body_never_contains_an_unmasked_account_ref(client: TestClient) -> None:
    alert_id = _new_alert(client)
    _login(client, "state_investigator")
    assert _hold(client, alert_id, "ACC-5", 100_000).status_code == 201

    d = _rows(client, DeliveryModel)[0]
    assert d.payload["account_ref"] == "ACC-5"  # the wire body to the bank carries the full ref
    assert "ACC-5" not in d.rendered_body  # the stored/viewable body does not
    assert "****" in d.rendered_body


def test_bank_nodal_is_denied_and_the_denial_is_audited(client: TestClient) -> None:
    alert_id = _new_alert(client)
    _login(client, "bank_nodal")

    r = _hold(client, alert_id, "ACC-5", 100_000)

    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN_PERMISSION"
    assert _rows(client, ActionModel) == []
    assert _rows(client, DeliveryModel) == []
    denied = [a for a in _rows(client, AuditEntryModel) if a.action == "action.denied"]
    assert len(denied) == 1 and denied[0].actor_role == "bank_nodal"
    assert client.get(f"/api/v1/alerts/{alert_id}").json()["status"] == "open"


def test_hold_above_disputed_is_rejected_with_lien_invalid(client: TestClient) -> None:
    alert_id = _new_alert(client)
    _login(client, "state_investigator")

    r = _hold(client, alert_id, "ACC-5", 480_001)

    assert r.status_code == 422
    assert r.json()["error"]["code"].startswith("LIEN_")
    assert _rows(client, ActionModel) == []
    assert _rows(client, DeliveryModel) == []


def test_hold_on_an_account_traced_from_no_complaint_is_rejected(client: TestClient) -> None:
    alert_id = _new_alert(client)
    _login(client, "state_investigator")

    r = client.post(
        f"/api/v1/alerts/{alert_id}/actions",
        json={"type": "request_hold", "params": {"account_id": "no-such", "proposed_paise": 1}},
    )

    assert r.status_code == 422 and r.json()["error"]["code"] == "LIEN_INVALID"


def test_override_needs_a_reason_and_a_second_action_on_an_actioned_alert_conflicts(
    client: TestClient,
) -> None:
    alert_id = _new_alert(client)
    _login(client, "i4c_analyst")

    no_reason = client.post(f"/api/v1/alerts/{alert_id}/actions", json={"type": "override"})
    assert no_reason.status_code == 422
    assert no_reason.json()["error"]["code"] == "ACTION_REASON_REQUIRED"

    ok = client.post(
        f"/api/v1/alerts/{alert_id}/actions",
        json={"type": "override", "reason": "known false positive"},
    )
    assert ok.status_code == 201 and ok.json()["status"] == "recorded"

    again = client.post(
        f"/api/v1/alerts/{alert_id}/actions", json={"type": "dispatch", "reason": "x"}
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "INVALID_TRANSITION"


def test_second_hold_cannot_exceed_what_is_left_of_the_disputed_amount(client: TestClient) -> None:
    first = _new_alert(client, "loc-1")
    second = _new_alert(client, "loc-2")
    _login(client, "state_investigator")
    assert _hold(client, first, "ACC-5", 400_000).status_code == 201

    r = _hold(client, second, "ACC-5", 100_000)  # only 80_000 of 480_000 remains

    assert r.status_code == 422 and r.json()["error"]["code"] == "LIEN_EXCEEDS_REMAINING"


# ---------------------------------------------------------------------------
# Outbox worker: retry with backoff, dead-letter, outbox view
# ---------------------------------------------------------------------------


class FailingChannel:
    def __init__(self) -> None:
        self.calls = 0

    def send(self, delivery: Delivery) -> DeliveryResult:
        self.calls += 1
        return DeliveryResult(ok=False, error="connection refused")


def _run_outbox(client: TestClient, channel, now: datetime) -> int:  # noqa: ANN001
    with _uow(client) as uow:
        assert uow.session is not None
        n = _service(client, uow.session).deliver_outbox({DeliveryChannel.WEBHOOK: channel}, now)
        uow.commit()
    return n


def test_backoff_sequence_is_exponential_and_capped() -> None:
    assert [backoff_seconds(n, 5.0) for n in range(1, 9)] == [5, 10, 20, 40, 80, 160, 300, 300]


def test_failing_channel_retries_with_backoff_then_dead_letters_and_shows_in_outbox_view(
    client: TestClient,
) -> None:
    alert_id = _new_alert(client)
    _login(client, "state_investigator")
    assert _hold(client, alert_id, "ACC-5", 100_000).status_code == 201
    created = _rows(client, DeliveryModel)[0].created_at
    channel = FailingChannel()

    now = created
    assert _run_outbox(client, channel, now) == 1  # attempt 1 fails
    d = _rows(client, DeliveryModel)[0]
    assert (d.status, d.attempts) == ("failed", 1)
    assert d.next_attempt_at == now + timedelta(seconds=5)

    assert _run_outbox(client, channel, now + timedelta(seconds=4)) == 0  # not due yet
    assert channel.calls == 1

    for gap, expected_attempts in ((5, 2), (10, 3), (20, 4)):
        now = now + timedelta(seconds=gap)
        assert _run_outbox(client, channel, now) == 1
        d = _rows(client, DeliveryModel)[0]
        assert d.attempts == expected_attempts and d.status == "failed"

    now = now + timedelta(seconds=40)
    assert _run_outbox(client, channel, now) == 1  # attempt 5 -> dead
    d = _rows(client, DeliveryModel)[0]
    assert (d.status, d.attempts, d.last_error) == ("dead", 5, "connection refused")

    assert _run_outbox(client, channel, now + timedelta(hours=1)) == 0  # dead is never retried
    assert channel.calls == 5

    view = client.get("/api/v1/outbox", params={"status": "dead"}).json()
    assert view["dead_count"] == 1
    assert [i["status"] for i in view["items"]] == ["dead"]
    assert view["items"][0]["last_error"] == "connection refused"
    assert "payload" not in view["items"][0]  # the wire body is never exposed


def test_a_successful_send_marks_the_delivery_sent(client: TestClient) -> None:
    alert_id = _new_alert(client)
    _login(client, "state_investigator")
    assert _hold(client, alert_id, "ACC-5", 100_000).status_code == 201

    class Ok:
        def send(self, delivery: Delivery) -> DeliveryResult:
            return DeliveryResult(ok=True, provider="bank-sim")

    now = _rows(client, DeliveryModel)[0].created_at
    assert _run_outbox(client, Ok(), now) == 1
    d = _rows(client, DeliveryModel)[0]
    assert (d.status, d.attempts, d.provider, d.sent_at) == ("sent", 1, "bank-sim", now)


def test_outbox_view_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/outbox").status_code == 401


def test_a_hold_request_delivery_cannot_exist_without_an_action(client: TestClient) -> None:
    alert_id = _new_alert(client)
    with pytest.raises(ValueError):
        Delivery(
            id="d1",
            alert_id=alert_id,
            action_id=None,
            channel=DeliveryChannel.WEBHOOK,
            webhook_kind=WebhookKind.HOLD_REQUEST,
            recipient="bank:b",
            rendered_body="",
            payload={},
            idempotency_key="k",
            status=DeliveryStatus.PENDING,
            attempts=0,
            next_attempt_at=T0,
            created_at=T0,
        )
    # ... and the database refuses it even if the entity check were bypassed.
    with _uow(client) as uow:
        assert uow.session is not None
        uow.session.add(
            DeliveryModel(
                id="d2",
                alert_id=alert_id,
                action_id=None,
                channel="webhook",
                webhook_kind="hold_request",
                recipient="bank:b",
                rendered_body="",
                payload={},
                idempotency_key="k2",
                status="pending",
                attempts=0,
                next_attempt_at=T0,
                created_at=T0,
            )
        )
        with pytest.raises(IntegrityError):
            uow.session.flush()


# ---------------------------------------------------------------------------
# Bank callback
# ---------------------------------------------------------------------------


def _callback(client: TestClient, request_id: str, status: str, at: str, **extra):  # noqa: ANN202
    return client.post(
        "/api/v1/integrations/bank/callbacks",
        json={"request_id": request_id, "status": status, "at_sim": at, **extra},
        headers=SERVICE_HEADERS,
    )


def _pending_hold(client: TestClient) -> tuple[str, str]:
    alert_id = _new_alert(client)
    _login(client, "state_investigator")
    r = _hold(client, alert_id, "ACC-5", 400_000)
    assert r.status_code == 201
    return alert_id, r.json()["id"]


def test_callback_requires_the_service_key(client: TestClient) -> None:
    _, request_id = _pending_hold(client)
    r = client.post(
        "/api/v1/integrations/bank/callbacks",
        json={"request_id": request_id, "status": "rejected", "at_sim": "2026-01-15T11:00:00Z"},
    )
    assert r.status_code == 401


def test_callback_updates_action_status_audits_and_appears_on_the_alert_timeline(
    client: TestClient,
) -> None:
    alert_id, request_id = _pending_hold(client)

    r = _callback(
        client, request_id, "applied", "2026-01-15T11:00:00Z", applied_amount_paise=350_000
    )

    assert r.status_code == 200 and r.json() == {"ack": True, "applied": True}
    (action,) = _rows(client, ActionModel)
    assert (action.status, action.applied_amount_paise) == ("applied", 350_000)
    assert any(a.action == "action.bank_callback" for a in _rows(client, AuditEntryModel))
    timeline = client.get(f"/api/v1/alerts/{alert_id}").json()["timeline"]
    assert any(t["text_code"] == "alert.hold.applied" for t in timeline)


def test_callback_arriving_twice_or_out_of_order_keeps_the_latest_sim_time(
    client: TestClient,
) -> None:
    _, request_id = _pending_hold(client)

    assert _callback(client, request_id, "released", "2026-01-15T13:00:00Z").json() == {
        "ack": True,
        "applied": True,
    }
    # an older "applied" arrives late: ignored
    late = _callback(
        client, request_id, "applied", "2026-01-15T11:00:00Z", applied_amount_paise=350_000
    )
    assert late.status_code == 200 and late.json()["applied"] is False
    # the exact same "released" again: ignored
    assert (
        _callback(client, request_id, "released", "2026-01-15T13:00:00Z").json()["applied"] is False
    )

    (action,) = _rows(client, ActionModel)
    assert action.status == "released"


def test_callback_rejects_an_applied_amount_above_the_proposal(client: TestClient) -> None:
    _, request_id = _pending_hold(client)

    r = _callback(
        client, request_id, "applied", "2026-01-15T11:00:00Z", applied_amount_paise=400_001
    )

    assert r.status_code == 422 and r.json()["error"]["code"] == "CALLBACK_INVALID"
    (action,) = _rows(client, ActionModel)
    assert action.status == "pending"


def test_callback_for_an_unknown_request_is_404(client: TestClient) -> None:
    r = _callback(client, "nope", "rejected", "2026-01-15T11:00:00Z")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# LC-6 signing, verified by a bank-shaped receiver over real HTTP (the round trip)
# ---------------------------------------------------------------------------


def test_signature_known_vector_and_window() -> None:
    body = b'{"a":1}'
    sig = sign("s3cret", "1700000000", body)
    assert len(sig) == 64
    assert verify("s3cret", "1700000000", body, sig)
    assert not verify("s3cret", "1700000000", body + b" ", sig)
    assert not verify("other", "1700000000", body, sig)
    assert within_window(1_700_000_000, 1_700_000_299)
    assert not within_window(1_700_000_000, 1_700_000_301)


class _Receiver(BaseHTTPRequestHandler):
    log: list[dict] = []

    def do_POST(self) -> None:  # noqa: N802
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        ts = self.headers["X-Nakabandi-Timestamp"]
        ok = verify(SECRET, ts, raw, self.headers["X-Nakabandi-Signature"]) and within_window(
            float(ts), SystemClock().now().timestamp()
        )
        self.log.append(
            {
                "path": self.path,
                "idempotency_key": self.headers["Idempotency-Key"],
                "timestamp": ts,
                "signature_valid": ok,
                "body": json.loads(raw),
            }
        )
        status = 200 if ok else 401
        payload = json.dumps({"ack": True} if ok else {"error": "invalid signature"}).encode()
        self.send_response(status)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - keep output quiet
        return


@pytest.fixture
def bank_receiver() -> Iterator[tuple[str, list[dict]]]:
    _Receiver.log = []
    server = HTTPServer(("127.0.0.1", 0), _Receiver)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/webhooks/nakabandi", _Receiver.log
    server.shutdown()
    server.server_close()


def test_hold_request_round_trip_signature_verifies_at_the_receiver(
    client: TestClient, bank_receiver: tuple[str, list[dict]]
) -> None:
    url, received = bank_receiver
    alert_id, request_id = _pending_hold(client)
    now = _rows(client, DeliveryModel)[0].created_at

    assert _run_outbox(client, BankWebhook(url, SECRET), now) == 1

    d = _rows(client, DeliveryModel)[0]
    assert (d.status, d.attempts) == ("sent", 1)
    assert len(received) == 1
    hit = received[0]
    assert hit["signature_valid"] is True
    assert hit["path"] == "/webhooks/nakabandi"
    assert hit["idempotency_key"] == f"hold_request:{request_id}"
    assert hit["body"]["kind"] == "hold_request" and hit["body"]["request_id"] == request_id
    assert hit["body"]["alert_ref"] == alert_id
    print("WEBHOOK ROUND-TRIP LOG:", json.dumps(hit, indent=2, sort_keys=True))

    # ... then the bank calls back and the action follows.
    r = _callback(
        client, request_id, "applied", "2026-01-15T11:00:00Z", applied_amount_paise=400_000
    )
    assert r.json()["applied"] is True


def test_a_wrong_secret_is_rejected_by_the_receiver_and_the_delivery_fails(
    client: TestClient, bank_receiver: tuple[str, list[dict]]
) -> None:
    url, received = bank_receiver
    _pending_hold(client)
    now = _rows(client, DeliveryModel)[0].created_at

    _run_outbox(client, BankWebhook(url, "wrong-secret"), now)

    d = _rows(client, DeliveryModel)[0]
    assert (d.status, d.last_error) == ("failed", "bank responded 401")
    assert received[0]["signature_valid"] is False
