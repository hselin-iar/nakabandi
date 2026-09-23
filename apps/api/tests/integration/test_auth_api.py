"""A4 Done When (DOC 4 Step A4): a tampered audit row makes /audit/verify fail; /auth/check
returns 204 or 403 as expected; login is rate limited. Plus a curl-equivalent smoke test of
login, /auth/me and /auth/check for two roles (Evidence required).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from nakabandi.audit.infrastructure.models import AuditEntryModel
from nakabandi.shared import SqlAlchemyUnitOfWork
from nakabandi.shared.infrastructure.db import create_sqlite_engine, make_session_factory
from sqlalchemy import select


def _login(client: TestClient, username: str, password: str) -> TestClient:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return client


def test_demo_users_are_seeded_and_listed(client: TestClient) -> None:
    r = client.get("/api/v1/auth/demo-users")
    assert r.status_code == 200
    roles = {u["role"] for u in r.json()}
    assert roles == {
        "i4c_analyst",
        "state_investigator",
        "district_officer",
        "bank_nodal",
        "demo_operator",
        "admin",
    }


def test_login_wrong_password_then_correct_password(client: TestClient) -> None:
    demo = client.get("/api/v1/auth/demo-users").json()
    admin = next(u for u in demo if u["role"] == "admin")

    bad = client.post(
        "/api/v1/auth/login", json={"username": admin["username"], "password": "not-it"}
    )
    assert bad.status_code == 401

    good = client.post(
        "/api/v1/auth/login",
        json={"username": admin["username"], "password": admin["password"]},
    )
    assert good.status_code == 200
    assert good.cookies.get("nakabandi_session") is not None


def test_auth_me_and_auth_check_for_two_roles(client: TestClient) -> None:
    demo = client.get("/api/v1/auth/demo-users").json()

    admin = next(u for u in demo if u["role"] == "admin")
    _login(client, admin["username"], admin["password"])
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "admin"
    assert "SIM_CONTROL" in me.json()["permissions"]

    ok = client.get("/api/v1/auth/check", params={"role": "admin"})
    assert ok.status_code == 204
    mismatch = client.get("/api/v1/auth/check", params={"role": "bank_nodal"})
    assert mismatch.status_code == 403

    client.post("/api/v1/auth/logout")

    bank = next(u for u in demo if u["role"] == "bank_nodal")
    _login(client, bank["username"], bank["password"])
    me2 = client.get("/api/v1/auth/me")
    assert me2.status_code == 200
    assert me2.json()["role"] == "bank_nodal"
    assert me2.json()["permissions"] == ["ACKNOWLEDGE", "VIEW_ALERTS"]

    ok2 = client.get("/api/v1/auth/check", params={"role": "bank_nodal"})
    assert ok2.status_code == 204
    mismatch2 = client.get("/api/v1/auth/check", params={"role": "admin"})
    assert mismatch2.status_code == 403


def test_auth_check_without_a_session_is_unauthenticated(client: TestClient) -> None:
    r = client.get("/api/v1/auth/check", params={"role": "admin"})
    assert r.status_code == 401


def test_login_is_rate_limited(client: TestClient) -> None:
    for _ in range(5):
        r = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "wrong"})
        assert r.status_code == 401

    sixth = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "wrong"})
    assert sixth.status_code == 429


def test_a_tampered_audit_row_makes_verify_fail(client: TestClient, db_url: str) -> None:
    demo = client.get("/api/v1/auth/demo-users").json()
    admin = next(u for u in demo if u["role"] == "admin")
    _login(client, admin["username"], admin["password"])

    ok = client.get("/api/v1/audit/verify")
    assert ok.status_code == 200
    assert ok.json()["ok"] is True

    session_factory = make_session_factory(create_sqlite_engine(db_url))
    with SqlAlchemyUnitOfWork(session_factory) as uow:
        assert uow.session is not None
        row = uow.session.scalar(select(AuditEntryModel).order_by(AuditEntryModel.seq).limit(1))
        assert row is not None
        row.payload = {"tampered": True}
        uow.commit()

    tampered = client.get("/api/v1/audit/verify")
    assert tampered.status_code == 200
    body = tampered.json()
    assert body["ok"] is False
    assert body["first_bad_seq"] is not None
