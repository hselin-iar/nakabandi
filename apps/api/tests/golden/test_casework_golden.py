"""A12 golden scenario (DOC 4 Done When): two complaints on one cluster give one case with both;
hash reports reproduce; a tampered audit row breaks verify and mismatches the pack's head hash;
non-LEA roles get masked refs. Real app, real SQLite, no bypass of use cases (DOC 3 A3 note) —
mirrors apps/api/tests/integration/test_live_chain.py's fixture shape.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from nakabandi.main import create_app
from sqlalchemy import text

HEADERS = {"X-Nakabandi-Service-Key": "test-only-service-key"}
BASE = datetime(2026, 1, 15, 4, 0, tzinfo=UTC)


def iso(minutes: float) -> str:
    return (BASE + timedelta(minutes=minutes)).isoformat()


def registry() -> dict:
    locations = [
        {
            "id": f"loc-{i + 1}",
            "kind": "ATM" if i % 2 == 0 else "BRANCH",
            "bank_id": "bank-1",
            "lat": 26.85 + i * 0.004,
            "lon": 80.95 + i * 0.004,
            "district_id": "demo-district-1",
            "cell_id": "cell-1",
            "source": "synthetic",
            "display_name": f"Location {i + 1}",
            "area_type": "urban",
            "activity_index": 0.5,
        }
        for i in range(6)
    ]
    return {
        "version": "casework-golden-v1",
        "banks": [{"id": "bank-1", "name": "Bank One", "short_code": "B1"}],
        "regions": [
            {"id": "st", "level": "state", "name": "State", "parent_id": None, "geojson_ref": None},
            {
                "id": "demo-district-1",
                "level": "district",
                "name": "District",
                "parent_id": "st",
                "geojson_ref": None,
            },
        ],
        "cells": [
            {
                "id": "cell-1",
                "grid_km": 5,
                "row": 1,
                "col": 1,
                "district_id": "demo-district-1",
                "centroid_lat": 26.86,
                "centroid_lon": 80.96,
            }
        ],
        "locations": locations,
        "units": [
            {
                "id": "u1",
                "kind": "station",
                "district_id": "demo-district-1",
                "lat": 26.851,
                "lon": 80.951,
                "status": "active",
            }
        ],
    }


def complaint(ref: str, account: str, at: float, *, home: str = "loc-1") -> dict:
    return {
        "batch_id": f"batch-{ref}",
        "idempotency_key": f"batch-{ref}",
        "sim_time": iso(at),
        "items": [
            {
                "external_ref": ref,
                "category": "upi_phishing",
                "amount_paise": 2_000_000,
                "victim_district_id": "demo-district-1",
                "credited_at": iso(at - 5),
                "reported_event_at": iso(at - 2),
                "observed_at": iso(at),
                "layer1_account": {
                    "account_ref": account,
                    "bank_id": "bank-1",
                    "home_location_id": home,
                },
            }
        ],
    }


def hops(ref: str, from_account: str, to_account: str, at: float, key: str) -> dict:
    return {
        "batch_id": key,
        "idempotency_key": key,
        "sim_time": iso(at),
        "items": [
            {
                "complaint_external_ref": ref,
                "from_account": {"account_ref": from_account, "bank_id": "bank-1"},
                "to_account": {"account_ref": to_account, "bank_id": "bank-1"},
                "amount_paise": 1_900_000,
                "layer": 2,
                "event_at": iso(at - 3),
                "observed_at": iso(at),
            }
        ],
    }


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("API_SERVICE_KEY", "test-only-service-key")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'casework.db'}")
    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-at-least-32-bytes-long")
    monkeypatch.setenv("NAKABANDI_EVIDENCE_STORE_PATH", str(tmp_path / "evidence"))
    with TestClient(create_app()) as c:
        yield c


def post(client: TestClient, path: str, body: dict) -> dict:
    r = client.post(f"/api/v1/ingest/{path}", json=body, headers=HEADERS)
    assert r.status_code == 200, r.text
    assert not r.json().get("rejected"), r.json()
    return r.json()


def login(client: TestClient, role: str = "i4c_analyst") -> None:
    users = client.get("/api/v1/auth/demo-users").json()
    user = next(u for u in users if u["role"] == role)
    r = client.post(
        "/api/v1/auth/login", json={"username": user["username"], "password": user["password"]}
    )
    assert r.status_code == 200, r.text


def rows(client: TestClient, sql: str, **params: object) -> list[tuple]:
    with client.app.state.session_factory() as session:  # type: ignore[attr-defined]
        return [tuple(r) for r in session.execute(text(sql), params)]


def build_two_complaint_cluster(client: TestClient) -> None:
    """c1 (a1 -> hop -> a2) then c2 (layer-1 a2 directly): one cluster, spaced 90 sim-minutes
    apart so casework's debounce (once per cluster per sim hour, config/policy.yaml) does not
    swallow the second rebuild."""
    post(client, "registry", registry())
    post(client, "complaints", complaint("gc1", "ga1", 10))
    post(client, "hops", hops("gc1", "ga1", "ga2", 15, "h-gc1"))
    post(client, "complaints", complaint("gc2", "ga2", 100))


def test_two_complaints_on_one_cluster_give_one_case_with_both(client: TestClient) -> None:
    build_two_complaint_cluster(client)
    login(client)

    assert rows(client, "SELECT DISTINCT cluster_id FROM cluster_members") != []
    cluster_id = rows(client, "SELECT DISTINCT cluster_id FROM cluster_members")[0][0]

    cases = client.get("/api/v1/cases").json()["items"]
    assert len(cases) == 1, "one cluster must give exactly one case"
    case = cases[0]
    assert case["cluster_ref"] == cluster_id
    assert case["complaint_count"] == 2
    assert case["victim_count"] == 2
    assert not case["single_complaint"]
    assert case["total_paise"] == 4_000_000

    detail = client.get(f"/api/v1/cases/{case['id']}").json()
    assert detail["id"] == case["id"]
    disclaimer = "Whether to register an FIR is the investigating officer's decision."
    assert disclaimer in detail["brief_md"]


def test_non_lea_role_gets_masked_refs_in_the_case(client: TestClient) -> None:
    build_two_complaint_cluster(client)
    login(client, role="district_officer")

    case = client.get("/api/v1/cases").json()["items"][0]
    refs = [a["masked_ref"] for a in case["accounts"]]
    assert refs, "the case must have accounts to mask"
    assert all(r.startswith("****") for r in refs), refs


def _first_alert_id(client: TestClient) -> str:
    alerts = client.get("/api/v1/alerts", params={"view": "all", "limit": 50}).json()["items"]
    assert alerts, "the golden scenario must raise at least one alert"
    return alerts[0]["id"]


def test_evidence_pack_versions_and_masks_for_non_lea(client: TestClient) -> None:
    build_two_complaint_cluster(client)
    login(client, role="i4c_analyst")
    alert_id = _first_alert_id(client)

    full = client.post(f"/api/v1/alerts/{alert_id}/evidence-pack")
    assert full.status_code == 200, full.text
    full_meta = full.json()

    login(client, role="district_officer")
    partial = client.post(f"/api/v1/alerts/{alert_id}/evidence-pack")
    assert partial.status_code == 200, partial.text
    partial_meta = partial.json()

    assert partial_meta["version"] == full_meta["version"] + 1  # packs are immutable, versioned

    pdf_full = client.get(full_meta["download_url"]).content
    pdf_partial = client.get(partial_meta["download_url"]).content
    assert pdf_full.startswith(b"%PDF")
    assert pdf_partial.startswith(b"%PDF")
    # the non-LEA build's stored bytes never contain an unmasked case account ref
    with client.app.state.session_factory() as session:  # type: ignore[attr-defined]
        refs = [r[0] for r in session.execute(text("SELECT account_ref FROM accounts")).all()]
    assert refs, "fixture must have accounts"
    assert not any(ref.encode() in pdf_partial for ref in refs if len(ref) > 4)


def test_tampered_audit_row_breaks_verify_and_mismatches_the_packs_head_hash(
    client: TestClient,
) -> None:
    build_two_complaint_cluster(client)
    login(client, role="i4c_analyst")
    alert_id = _first_alert_id(client)

    built = client.post(f"/api/v1/alerts/{alert_id}/evidence-pack")
    assert built.status_code == 200, built.text
    pack_head_hash = built.json()["audit_head_hash"]

    verify_before = client.get("/api/v1/audit/verify").json()
    assert verify_before["ok"] is True
    assert verify_before["head_hash"] == pack_head_hash

    with client.app.state.session_factory() as session:  # type: ignore[attr-defined]
        session.execute(
            text("UPDATE audit_entries SET payload = '{\"tampered\": true}' WHERE seq = 1")
        )
        session.commit()

    verify_after = client.get("/api/v1/audit/verify").json()
    assert verify_after["ok"] is False
    assert verify_after["head_hash"] != pack_head_hash
