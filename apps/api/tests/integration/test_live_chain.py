"""The LIVE chain (DOC 4 Checkpoint 3): a complaint posted to /ingest yields a real forecast and a
real alert, with no test doubles between the API and the modules.

    POST /ingest/complaints -> graph.resolve -> forecast.generate -> interception.assess
                            -> alerting.raise_or_merge -> analytics projectors, in one request

The world is small and hand-built: six locations (an ATM/BRANCH mix) around one cell, two response
units, one bank. Cash-out history at loc-1 makes the cluster's next forecast concentrate on it.
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
BASE = datetime(2026, 1, 15, 4, 30, tzinfo=UTC)


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
            "district_id": "d1",
            "cell_id": "cell-1",
            "source": "synthetic",
            "display_name": f"Location {i + 1}",
            "area_type": "urban",
            "activity_index": 0.5,
        }
        for i in range(6)
    ]
    return {
        "version": "live-v1",
        "banks": [{"id": "bank-1", "name": "Bank One", "short_code": "B1"}],
        "regions": [
            {"id": "st", "level": "state", "name": "State", "parent_id": None, "geojson_ref": None},
            {
                "id": "d1",
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
                "district_id": "d1",
                "centroid_lat": 26.86,
                "centroid_lon": 80.96,
            }
        ],
        "locations": locations,
        "units": [
            {
                "id": "u1",
                "kind": "station",
                "district_id": "d1",
                "lat": 26.851,
                "lon": 80.951,
                "status": "active",
            },
            {
                "id": "u2",
                "kind": "cyber_cell",
                "district_id": "d1",
                "lat": 26.87,
                "lon": 80.97,
                "status": "active",
            },
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
                "victim_district_id": "d1",
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


def cash_outs(account: str, location: str, count: int, first_at: float, key: str) -> dict:
    return {
        "batch_id": key,
        "idempotency_key": key,
        "sim_time": iso(first_at + 3 * count),
        "items": [
            {
                "account_ref": account,
                "location_id": location,
                "channel": "ATM",
                "amount_paise": 100_000 * (k + 1),
                "event_at": iso(first_at + 3 * k),
                "observed_at": iso(first_at + 3 * k + 2),
                "source": "bank_report",
            }
            for k in range(count)
        ],
    }


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("API_SERVICE_KEY", "test-only-service-key")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'live.db'}")
    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-at-least-32-bytes-long")
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


def alerts(client: TestClient) -> list[dict]:
    r = client.get("/api/v1/alerts", params={"view": "all", "limit": 200})
    assert r.status_code == 200, r.text
    return r.json()["items"]


def location_probs(client: TestClient, complaint_ref: str) -> dict[str, float]:
    """The location-level probabilities of a complaint's FIRST forecast."""
    found = rows(
        client,
        "SELECT i.items_json FROM forecast_level_items i JOIN forecasts f ON f.id = i.forecast_id "
        "JOIN complaints c ON c.id = f.complaint_id "
        "WHERE c.external_ref = :ref AND i.resolution = 'location' ORDER BY f.generated_at, f.id",
        ref=complaint_ref,
    )
    import json

    return {i["id"]: i["prob"] for i in json.loads(found[0][0])}


def build_world(client: TestClient) -> None:
    """registry, c1 (cold), its hops, six cash-outs at loc-1, then c2 through a reused mule."""
    post(client, "registry", registry())
    post(client, "complaints", complaint("c1", "a1", 10))
    post(client, "hops", hops("c1", "a1", "a2", 15, "h-c1"))
    post(client, "cashout-observations", cash_outs("a2", "loc-1", 6, 20, "obs-1"))
    post(client, "complaints", complaint("c2", "a2", 60))


# ---------------------------------------------------------------------------
# Checkpoint 3
# ---------------------------------------------------------------------------


def test_a_posted_complaint_becomes_a_real_alert_with_its_forecast_attached(
    client: TestClient,
) -> None:
    build_world(client)
    login(client)

    listed = alerts(client)
    assert listed, "a complaint posted through /ingest must produce an alert (Checkpoint 3)"
    detail = client.get(f"/api/v1/alerts/{listed[0]['id']}").json()

    forecast = detail["forecast"]
    assert forecast is not None  # "at least one alert with a forecast attached"
    assert set(forecast["levels"]) == {"district", "cell", "location"}
    assert forecast["model_versions"]["scorer"] and not forecast["stale"]
    assert 0 < forecast["timing"]["p120"] <= 1
    assert forecast["evidence"], "the forecast explains itself"
    location_level = forecast["levels"]["location"]
    assert not location_level["abstained"]
    assert sum(i["prob"] for i in location_level["items"]) == pytest.approx(1.0, abs=1e-6)

    assert detail["interception"], "and the interception assessment behind it"
    assessment = detail["interception"][0]
    assert assessment["best_unit"] is not None and assessment["best_unit"]["eta_min"] > 0
    assert assessment["verdict"] in {"INTERCEPTABLE", "MARGINAL", "NOT_INTERCEPTABLE"}
    assert assessment["forecast_id"] == forecast["id"]

    # every complaint went all the way through
    assert rows(client, "SELECT external_ref, processing_status FROM complaints ORDER BY 1") == [
        ("c1", "processed"),
        ("c2", "processed"),
    ]


def test_an_alert_targets_only_a_location_the_forecast_is_sure_enough_about(
    client: TestClient,
) -> None:
    post(client, "registry", registry())
    post(client, "complaints", complaint("c1", "a1", 10))  # a cold cluster: only its home is known
    login(client)

    probs = location_probs(client, "c1")
    targets = {a["target"]["id"]: a for a in alerts(client)}

    # loc-1 (home) leads; the others are below the alert floor / the ladder's action confidence,
    # so they are not alerts, and the alert's confidence is THAT target's probability
    assert max(probs, key=lambda loc: probs[loc]) == "loc-1"
    assert set(targets) == {"loc-1"}
    assert targets["loc-1"]["confidence"] == pytest.approx(probs["loc-1"], abs=1e-6)
    assert targets["loc-1"]["confidence"] < 0.9  # not the district level's near-1.0
    assert targets["loc-1"]["target"]["name"] == "Location 1"  # the registry's name, not blank


def test_cash_out_history_reaches_the_next_forecast_of_the_same_cluster(client: TestClient) -> None:
    build_world(client)

    cold, informed = location_probs(client, "c1"), location_probs(client, "c2")

    assert rows(client, "SELECT location_id, observation_count FROM cluster_location_stats") == [
        ("loc-1", 6)
    ]
    assert informed["loc-1"] > 0.9 > cold["loc-1"]  # six cash-outs at loc-1 concentrated it


def test_the_second_complaint_joined_the_first_ones_cluster(client: TestClient) -> None:
    build_world(client)

    clusters = rows(client, "SELECT DISTINCT cluster_id FROM cluster_members")
    assert len(clusters) == 1  # c1's a1, a2 and c2's layer-1 account a2 are one cluster


# ---------------------------------------------------------------------------
# A10 Done When: a confirmed hit changes the next forecast
# ---------------------------------------------------------------------------


def _world_with_optional_confirmation(client: TestClient, confirm: bool) -> dict[str, float]:
    post(client, "registry", registry())
    post(client, "complaints", complaint("c1", "a1", 10))
    post(client, "hops", hops("c1", "a1", "a2", 15, "h-c1"))
    login(client)
    if confirm:
        (alert,) = alerts(client)  # the one alert c1's cold forecast raised (at loc-1)
        for result in ("hit", "late"):  # two distinct marks: two confirmed cash-outs at loc-4
            r = client.post(
                f"/api/v1/alerts/{alert['id']}/outcome",
                json={"result": result, "location_id": "loc-4", "reason": "seen at the ATM"},
            )
            assert r.status_code == 201, r.text
    post(client, "complaints", complaint("c2", "a2", 60))  # a reused mule: same cluster
    return location_probs(client, "c2")


def test_a_confirmed_hit_changes_the_next_forecast_for_that_cluster(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("API_SERVICE_KEY", "test-only-service-key")
    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-at-least-32-bytes-long")

    def run(confirm: bool) -> tuple[dict[str, float], list[tuple]]:
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / f'confirm-{confirm}.db'}")
        with TestClient(create_app()) as client:
            probs = _world_with_optional_confirmation(client, confirm)
            stats = rows(
                client, "SELECT location_id, observation_count FROM cluster_location_stats"
            )
        return probs, stats

    without, stats_without = run(confirm=False)
    with_confirmation, stats_with = run(confirm=True)

    assert stats_without == []
    assert stats_with == [("loc-4", 2)]  # the officer's confirmations are in the cluster's affinity
    # ... and the next forecast sees them (a level that abstains has no items: 0)
    assert with_confirmation.get("loc-4", 0.0) > without.get("loc-4", 0.0)


# ---------------------------------------------------------------------------
# Hops that arrive later; duplicates; failure and retry
# ---------------------------------------------------------------------------


def test_hops_that_arrive_later_refresh_the_forecast_and_the_alert_merges(
    client: TestClient,
) -> None:
    post(client, "registry", registry())
    post(client, "complaints", complaint("c1", "a1", 10))
    login(client)
    (before,) = alerts(client)

    post(client, "hops", hops("c1", "a1", "a2", 15, "h-c1"))

    (after,) = alerts(client)  # still ONE alert: the refresh merged into it
    assert after["id"] == before["id"]
    assert rows(client, "SELECT COUNT(*) FROM forecasts") == [(2,)]  # c1 was forecast again
    timeline = client.get(f"/api/v1/alerts/{after['id']}").json()["timeline"]
    assert "alert.merged" in [t["text_code"] for t in timeline]


def test_a_refresh_does_not_count_the_complaint_twice_on_the_heatmap(client: TestClient) -> None:
    post(client, "registry", registry())
    post(client, "complaints", complaint("c1", "a1", 10))
    post(client, "hops", hops("c1", "a1", "a2", 15, "h-c1"))  # a refresh: a 2nd forecast for c1
    login(client)

    r = client.get(
        "/api/v1/analytics/heatmap",
        params={"layer": "potential", "level": "location", "to": iso(30)},
    )

    by_id = {c["id"]: c["alert_count"] for c in r.json()["cells"]}
    assert by_id["loc-1"] == 1  # one contributing forecast, not two


def test_a_duplicate_or_replayed_complaint_adds_no_alert_and_no_forecast(
    client: TestClient,
) -> None:
    post(client, "registry", registry())
    post(client, "complaints", complaint("c1", "a1", 10))
    forecasts, alert_ids = (
        rows(client, "SELECT COUNT(*) FROM forecasts")[0][0],
        {r[0] for r in rows(client, "SELECT id FROM alerts")},
    )

    post(client, "complaints", complaint("c1", "a1", 10))  # the same batch again (replay)
    other = complaint("c1", "a1", 10)
    other["idempotency_key"] = other["batch_id"] = "another-key"
    post(client, "complaints", other)  # same external_ref, new batch (idempotent duplicate)

    assert rows(client, "SELECT COUNT(*) FROM forecasts")[0][0] == forecasts
    assert {r[0] for r in rows(client, "SELECT id FROM alerts")} == alert_ids


def test_a_failing_stage_leaves_the_complaint_unprocessed_and_retry_recovers_it(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from nakabandi import live_pipeline

    post(client, "registry", registry())
    real = live_pipeline.LiveForecaster.generate

    def broken(self, ctx, as_of):  # noqa: ANN001, ANN202
        raise RuntimeError("model store unavailable")

    monkeypatch.setattr(live_pipeline.LiveForecaster, "generate", broken)
    post(client, "complaints", complaint("c1", "a1", 10))  # the ingest itself still succeeds

    assert rows(client, "SELECT processing_status, failed_stage FROM complaints") == [
        ("unprocessed", "forecast.generate")
    ]
    login(client)
    assert alerts(client) == []

    monkeypatch.setattr(live_pipeline.LiveForecaster, "generate", real)
    assert client.app.state.run_retry_once() == 1  # type: ignore[attr-defined]

    assert rows(client, "SELECT processing_status, failed_stage FROM complaints") == [
        ("processed", None)
    ]
    assert len(alerts(client)) == 1


def test_merging_two_clusters_rekeys_their_alerts_and_closes_the_duplicate(
    client: TestClient,
) -> None:
    post(client, "registry", registry())
    post(client, "complaints", complaint("c1", "a1", 10))
    post(client, "complaints", complaint("c2", "a5", 20))  # a different mule: its own cluster
    login(client)
    assert len([a for a in alerts(client) if a["status"] == "open"]) == 2  # one alert per cluster

    post(client, "hops", hops("c2", "a5", "a1", 30, "h-join"))  # c2's money reached c1's mule

    statuses = sorted(a["status"] for a in alerts(client))
    assert statuses == ["closed", "open"]  # the newer duplicate closed as merged (DOC 3 M4)


def test_the_units_come_from_geo_and_the_interceptor_uses_them(client: TestClient) -> None:
    post(client, "registry", registry())
    post(client, "complaints", complaint("c1", "a1", 10))

    (row,) = rows(
        client,
        "SELECT best_unit_id, best_unit_eta_min FROM intercept_assessments "
        "WHERE target_id = 'loc-1'",
    )

    assert row[0] == "u1" and row[1] > 0  # the nearest of geo's two registered units


def test_a_cluster_merge_carries_its_cash_out_history_to_the_survivor(client: TestClient) -> None:
    post(client, "registry", registry())
    post(client, "complaints", complaint("c1", "a1", 10))
    post(client, "complaints", complaint("c2", "a5", 20))  # two separate clusters
    post(client, "cashout-observations", cash_outs("a1", "loc-2", 3, 30, "obs-a1"))
    post(client, "cashout-observations", cash_outs("a5", "loc-3", 2, 50, "obs-a5"))
    before = rows(
        client, "SELECT cluster_id, location_id, observation_count FROM cluster_location_stats"
    )
    assert len({b[0] for b in before}) == 2  # each cluster has history of its own

    post(client, "hops", hops("c2", "a5", "a1", 70, "h-join"))  # c2's money reached c1's mule

    after = rows(
        client, "SELECT cluster_id, location_id, observation_count FROM cluster_location_stats"
    )
    assert len({a[0] for a in after}) == 1  # one cluster now holds both histories
    assert sorted((a[1], a[2]) for a in after) == [("loc-2", 3), ("loc-3", 2)]
