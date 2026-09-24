"""A9 Done When (DOC 4 Step A9): rollups from the golden run match the hand-computed fixture;
filters change results; a district_officer sees only their district; small-count cells are
suppressed above location level; repeated identical queries return 304.

The "golden run": three forecasts and five alerts on a small hand-built registry, driven through
the real projectors (ForecastGenerated / AlertRaised on a real EventBus, on the publisher's own
session). Every expected number below is worked out by hand in the comments.

Registry (bank / district / cell):
  loc-1  demo-bank-1  demo-district-1  cell-1        loc-4  demo-bank-1  d-other  cell-3
  loc-2  bank-2       demo-district-1  cell-1        loc-5  bank-2       d-far    cell-4
  loc-3  demo-bank-1  demo-district-1  cell-2
  districts demo-district-1, d-other under state demo-state-1; d-far under state st-2

Forecasts (complaint, category, confidence, p120, generated at, then location | cell items):
  f1  c1 upi_phishing    0.90 (band 3)  0.5  12:10
        loc-1 .5, loc-2 .3, loc-3 .2 | cell-1 .8, cell-2 .2
  f2  c2 digital_arrest  0.50 (band 1)  0.4  13:20
        loc-1 .25, loc-4 .75 | cell-1 .5, cell-3 .5
  f3  c3 investment_scam 0.70 (band 2)  1.0  12:40
        loc-5 1.0 | cell-4 1.0

Alerts (each one from its forecast's complaint; mass = the target's item prob x p120):
  a1 12:15 loc-1 (f1)  .5x.5  = 0.25     a4 13:25 loc-4 (f2)  .75x.4 = 0.30
  a2 12:15 loc-2 (f1)  .3x.5  = 0.15     a5 12:45 loc-5 (f3)  1.0x1.0 = 1.00
  a3 13:25 loc-1 (f2)  .25x.4 = 0.10
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alerting.test_use_cases import FakeAssessment, FakeForecast, FakeTarget
from fastapi.testclient import TestClient
from nakabandi.alerting import AlertService
from nakabandi.forecast import Forecast, LevelForecast, TimingForecast
from nakabandi.forecast.domain.types import RankedItem
from nakabandi.forecast.infrastructure.repositories import SqlForecastRepo
from nakabandi.geo import LocationScopeLookup
from nakabandi.intake import IngestHooks
from nakabandi.intake.infrastructure.models import ComplaintModel
from nakabandi.main import create_app
from nakabandi.shared import ForecastGenerated, SqlAlchemyUnitOfWork, new_id
from nakabandi_contracts.enums import Resolution
from sqlalchemy import select

SERVICE_HEADERS = {"X-Nakabandi-Service-Key": "test-only-service-key"}


def _at(h: int, m: int = 0) -> datetime:
    return datetime(2026, 1, 15, h, m, tzinfo=UTC)


def _region(id_: str, level: str, name: str, parent: str | None) -> dict:
    return {"id": id_, "level": level, "name": name, "parent_id": parent, "geojson_ref": None}


def _cell(id_: str, district: str, row: int, lat: float, lon: float) -> dict:
    return {
        "id": id_,
        "grid_km": 5,
        "row": row,
        "col": row,
        "district_id": district,
        "centroid_lat": lat,
        "centroid_lon": lon,
    }


def _loc(id_: str, bank: str, district: str, cell: str, lat: float, lon: float, kind: str) -> dict:
    return {
        "id": id_,
        "kind": kind,
        "bank_id": bank,
        "lat": lat,
        "lon": lon,
        "district_id": district,
        "cell_id": cell,
        "source": "synthetic",
        "display_name": f"Location {id_}",
        "area_type": "urban",
        "activity_index": 0.5,
    }


REGISTRY = {
    "version": "heat-v1",
    "banks": [
        {"id": "demo-bank-1", "name": "Demo Bank One", "short_code": "DB1"},
        {"id": "bank-2", "name": "Bank Two", "short_code": "B2"},
    ],
    "regions": [
        _region("demo-state-1", "state", "State One", None),
        _region("st-2", "state", "State Two", None),
        _region("demo-district-1", "district", "District One", "demo-state-1"),
        _region("d-other", "district", "District Other", "demo-state-1"),
        _region("d-far", "district", "District Far", "st-2"),
    ],
    "cells": [
        _cell("cell-1", "demo-district-1", 1, 26.85, 80.95),
        _cell("cell-2", "demo-district-1", 2, 26.90, 81.00),
        _cell("cell-3", "d-other", 3, 27.20, 81.20),
        _cell("cell-4", "d-far", 4, 12.97, 77.59),
    ],
    "locations": [
        _loc("loc-1", "demo-bank-1", "demo-district-1", "cell-1", 26.85, 80.95, "ATM"),
        _loc("loc-2", "bank-2", "demo-district-1", "cell-1", 26.86, 80.96, "BRANCH"),
        _loc("loc-3", "demo-bank-1", "demo-district-1", "cell-2", 26.90, 81.00, "AGENT"),
        _loc("loc-4", "demo-bank-1", "d-other", "cell-3", 27.20, 81.20, "ATM"),
        _loc("loc-5", "bank-2", "d-far", "cell-4", 12.97, 77.59, "ATM"),
    ],
    "units": [],
}

COMPLAINTS = {  # the mini fixture's complaints: c1 upi_phishing, c2 digital_arrest, c3 investment
    "batch_id": "heat-complaints",
    "idempotency_key": "heat-complaints",
    "sim_time": "2026-01-15T10:00:00+05:30",
    "items": [
        {
            "external_ref": ref,
            "category": cat,
            "amount_paise": amount,
            "victim_district_id": "demo-district-1",
            "credited_at": "2026-01-15T09:50:00+05:30",
            "reported_event_at": "2026-01-15T09:55:00+05:30",
            "observed_at": "2026-01-15T10:00:00+05:30",
            "layer1_account": {"account_ref": f"acc-{ref}", "bank_id": "demo-bank-1"},
        }
        for ref, cat, amount in (
            ("c1", "upi_phishing", 500_000),
            ("c2", "digital_arrest", 1_200_000),
            ("c3", "investment_scam", 800_000),
        )
    ],
}


# ---------------------------------------------------------------------------
# Building the golden run
# ---------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("API_SERVICE_KEY", "test-only-service-key")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'heat.db'}")
    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-at-least-32-bytes-long")
    with TestClient(create_app()) as c:
        # The golden run drives forecasts and alerts by hand; keep the live chain out of it.
        c.app.state.ingest_hooks_factory = lambda _session, _bus: IngestHooks()  # type: ignore[attr-defined]
        for path, body in (("registry", REGISTRY), ("complaints", COMPLAINTS)):
            r = c.post(f"/api/v1/ingest/{path}", json=body, headers=SERVICE_HEADERS)
            assert r.status_code == 200 and not r.json().get("rejected"), r.text
        yield c


def _uow(client: TestClient) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(client.app.state.session_factory)  # type: ignore[attr-defined]


def _login(client: TestClient, role: str) -> None:
    users = client.get("/api/v1/auth/demo-users").json()
    user = next(u for u in users if u["role"] == role)
    r = client.post(
        "/api/v1/auth/login", json={"username": user["username"], "password": user["password"]}
    )
    assert r.status_code == 200, r.text


def _forecast(
    complaint_id: str,
    at: datetime,
    confidence: float,
    p120: float,
    cells: list[tuple[str, float]],
    locs: list[tuple[str, float]],
) -> Forecast:
    def level(res: Resolution, items: list[tuple[str, float]]) -> LevelForecast:
        return LevelForecast(
            resolution=res,
            abstained=False,
            confidence=confidence,
            items=[RankedItem(id=i, prob=p, rank=r + 1) for r, (i, p) in enumerate(items)],
        )

    return Forecast(
        id=new_id(),
        complaint_id=complaint_id,
        cluster_id=f"cl-{complaint_id}",
        generated_at=at,
        model_versions={"scorer": "test", "timing": "test"},
        levels={
            Resolution.CELL.value: level(Resolution.CELL, cells),
            Resolution.LOCATION.value: level(Resolution.LOCATION, locs),
        },
        timing=TimingForecast(
            weights=[0.5, 0.5],
            medians_min=[30.0, 90.0],
            sigmas=[0.5, 0.5],
            elapsed_min=0.0,
            residual_mass=1.0,
            p30=p120 / 3,
            p60=p120 / 2,
            p120=p120,
        ),
        confidence=confidence,
        novelty=0.0,
        stale=False,
    )


def _complaint_ids(client: TestClient) -> dict[str, str]:
    with _uow(client) as uow:
        assert uow.session is not None
        rows = uow.session.execute(select(ComplaintModel.external_ref, ComplaintModel.id))
        return {ref: id_ for ref, id_ in rows}


def _publish_forecast(client: TestClient, forecast: Forecast) -> None:
    """What pipeline.ProcessComplaint does after generating: save, then publish."""
    st = client.app.state  # type: ignore[attr-defined]
    with _uow(client) as uow:
        assert uow.session is not None
        SqlForecastRepo(uow.session).save(forecast)
        st.event_bus_factory(uow.session).publish(
            ForecastGenerated(
                event_id=new_id(),
                occurred_at=forecast.generated_at,
                forecast_id=forecast.id,
                complaint_id=forecast.complaint_id,
            )
        )
        uow.commit()


def _raise_alert(client: TestClient, at: datetime, complaint_id: str, target: str) -> None:
    st = client.app.state  # type: ignore[attr-defined]
    st.clock.advance_to(at)
    with _uow(client) as uow:
        assert uow.session is not None
        AlertService(
            session=uow.session,
            clock=st.clock,
            policy=st.policy,
            role_permissions=st.role_permissions,
            sse_hub=st.sse_hub,
            scope_lookup=LocationScopeLookup(uow.session),
            bus=st.event_bus_factory(uow.session),
        ).raise_or_merge(
            FakeForecast(id=new_id(), complaint_id=complaint_id, cluster_id=f"cl-{complaint_id}"),
            [FakeAssessment(target=FakeTarget(id=target))],
        )
        uow.commit()


@pytest.fixture
def golden(client: TestClient) -> TestClient:
    c = _complaint_ids(client)
    _publish_forecast(
        client,
        _forecast(
            c["c1"],
            _at(12, 10),
            0.90,
            0.5,
            [("cell-1", 0.8), ("cell-2", 0.2)],
            [("loc-1", 0.5), ("loc-2", 0.3), ("loc-3", 0.2)],
        ),
    )
    _publish_forecast(
        client,
        _forecast(
            c["c2"],
            _at(13, 20),
            0.50,
            0.4,
            [("cell-1", 0.5), ("cell-3", 0.5)],
            [("loc-1", 0.25), ("loc-4", 0.75)],
        ),
    )
    _publish_forecast(
        client,
        _forecast(c["c3"], _at(12, 40), 0.70, 1.0, [("cell-4", 1.0)], [("loc-5", 1.0)]),
    )
    _raise_alert(client, _at(12, 15), c["c1"], "loc-1")
    _raise_alert(client, _at(12, 15), c["c1"], "loc-2")
    _raise_alert(client, _at(12, 45), c["c3"], "loc-5")
    _raise_alert(client, _at(13, 25), c["c2"], "loc-1")
    _raise_alert(client, _at(13, 25), c["c2"], "loc-4")
    client.app.state.clock.advance_to(_at(14, 0))  # type: ignore[attr-defined]
    _login(client, "i4c_analyst")
    return client


def _map(client: TestClient, **params: object) -> dict:
    r = client.get("/api/v1/analytics/heatmap", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _by_id(body: dict) -> dict[str, tuple[float, int]]:
    return {c["id"]: (c["value"], c["alert_count"]) for c in body["cells"]}


# ---------------------------------------------------------------------------
# Rollups match the hand-computed fixture
# ---------------------------------------------------------------------------


def test_live_locations_match_the_hand_computed_rollup(golden: TestClient) -> None:
    body = _map(golden, layer="live", level="location")

    got = _by_id(body)
    assert set(got) == {"loc-1", "loc-2", "loc-4", "loc-5"}
    assert got["loc-1"] == (pytest.approx(0.25 + 0.10), 2)  # a1 + a3
    assert got["loc-2"] == (pytest.approx(0.15), 1)
    assert got["loc-4"] == (pytest.approx(0.30), 1)
    assert got["loc-5"] == (pytest.approx(1.00), 1)
    assert body["suppressed_count"] == 0  # never suppressed at location level
    assert body["legend"]["min"] == pytest.approx(0.15) and body["legend"]["max"] == 1.0
    print("SAMPLE 1 (live, location, no filters):", body)


def test_live_cells_are_summed_from_locations_and_small_counts_are_suppressed(
    golden: TestClient,
) -> None:
    body = _map(golden, layer="live", level="cell")

    # cell-1 = loc-1 + loc-2 = 0.25+0.10+0.15 = 0.50 over 3 alerts (k = 3: kept);
    # cell-3 (1 alert) and cell-4 (1 alert) are below k and suppressed.
    assert _by_id(body) == {"cell-1": (pytest.approx(0.50), 3)}
    assert body["suppressed_count"] == 2
    assert (body["cells"][0]["lat"], body["cells"][0]["lon"]) == (26.85, 80.95)


def test_live_districts_roll_up_and_suppress(golden: TestClient) -> None:
    body = _map(golden, layer="live", level="district")

    assert _by_id(body) == {"demo-district-1": (pytest.approx(0.50), 3)}
    assert body["cells"][0]["name"] == "District One"
    # the district sits at the mean of its cells' centroids: (26.85+26.90)/2, (80.95+81.00)/2
    assert body["cells"][0]["lat"] == pytest.approx(26.875)
    assert body["cells"][0]["lon"] == pytest.approx(80.975)
    assert body["suppressed_count"] == 2  # d-other, d-far


def test_potential_layer_is_the_decayed_forecast_mass(golden: TestClient) -> None:
    body = _map(golden, layer="potential", level="location")  # now = 14:00, half-life 24 h

    d2, d1 = 0.5 ** (2 / 24), 0.5 ** (1 / 24)  # decay after 2 h and after 1 h
    got = _by_id(body)
    # loc-1: f1 (12:00 bucket, 2 h old) .5x.5 = .25 ; f2 (13:00 bucket, 1 h old) .25x.4 = .10
    assert got["loc-1"] == (pytest.approx(0.25 * d2 + 0.10 * d1), 2)
    assert got["loc-5"] == (pytest.approx(1.0 * d2), 1)  # f3, 12:00 bucket
    assert got["loc-4"] == (pytest.approx(0.30 * d1), 1)  # f2, 13:00 bucket
    assert "persistence estimate" in body["legend"]["note"].lower()


def test_potential_cells_below_k_forecasts_are_suppressed(golden: TestClient) -> None:
    body = _map(golden, layer="potential", level="cell")

    # cell-1 has two contributing forecasts (f1, f2), every other cell one: all below k = 3.
    assert body["cells"] == [] and body["suppressed_count"] == 4


# ---------------------------------------------------------------------------
# Filters change results
# ---------------------------------------------------------------------------


def test_category_filter(golden: TestClient) -> None:
    body = _map(golden, layer="live", level="location", category="upi_phishing")
    assert _by_id(body) == {"loc-1": (pytest.approx(0.25), 1), "loc-2": (pytest.approx(0.15), 1)}
    print("SAMPLE 2 (live, location, category=upi_phishing):", body)


def test_min_confidence_filter_uses_the_policy_confidence_bands(golden: TestClient) -> None:
    # 0.6 -> band 2: keeps a1, a2 (0.90, band 3) and a5 (0.70, band 2); drops a3, a4 (0.50, band 1)
    body = _map(golden, layer="live", level="location", min_confidence=0.6)
    assert _by_id(body) == {
        "loc-1": (pytest.approx(0.25), 1),
        "loc-2": (pytest.approx(0.15), 1),
        "loc-5": (pytest.approx(1.0), 1),
    }


def test_amount_band_filter_uses_the_policy_amount_bands(golden: TestClient) -> None:
    # every complaint is below the first policy boundary (5,000,000 paise): band 0
    assert len(_map(golden, layer="live", level="location", amount_band=0)["cells"]) == 4
    assert _map(golden, layer="live", level="location", amount_band=1)["cells"] == []


def test_time_window_selects_hour_buckets(golden: TestClient) -> None:
    body = _map(
        golden,
        layer="live",
        level="location",
        **{"from_": "2026-01-15T12:00:00Z", "to": "2026-01-15T12:59:00Z"},
    )
    assert set(_by_id(body)) == {"loc-1", "loc-2", "loc-5"}  # a3, a4 fall in the 13:00 bucket


def test_state_and_bbox_filters(golden: TestClient) -> None:
    assert set(_by_id(_map(golden, layer="live", level="location", state="st-2"))) == {"loc-5"}
    near_lucknow = "80.9,26.8,81.1,27.0"  # min_lon,min_lat,max_lon,max_lat: loc-1, loc-2, loc-3
    assert set(_by_id(_map(golden, layer="live", level="location", bbox=near_lucknow))) == {
        "loc-1",
        "loc-2",
    }


def test_timeseries_sums_per_hour(golden: TestClient) -> None:
    r = golden.get("/api/v1/analytics/timeseries", params={"layer": "live"})
    assert r.status_code == 200
    points = {p["hour"][:13]: (p["value"], p["alert_count"]) for p in r.json()["points"]}
    assert points == {
        "2026-01-15T12": (pytest.approx(0.25 + 0.15 + 1.0), 3),
        "2026-01-15T13": (pytest.approx(0.10 + 0.30), 2),
    }


def test_live_metrics_summarise_the_last_24_hours(golden: TestClient) -> None:
    m = golden.get("/api/v1/analytics/live-metrics").json()
    assert m["alert_count"] == 5 and m["active_locations"] == 4
    assert m["expected_mass"] == pytest.approx(1.80)


def test_no_data_is_an_empty_map_not_an_error(client: TestClient) -> None:
    _login(client, "i4c_analyst")
    body = _map(client, layer="live", level="cell")
    assert body["cells"] == [] and body["suppressed_count"] == 0
    assert body["legend"]["min"] == 0 and body["legend"]["max"] == 0


def test_invalid_filters_are_a_422_with_field_details(client: TestClient) -> None:
    _login(client, "i4c_analyst")
    r = client.get(
        "/api/v1/analytics/heatmap",
        params={"from_": "2026-01-16T00:00:00Z", "to": "2026-01-15T00:00:00Z"},
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "HEAT_FILTER_INVALID"
    assert r.json()["error"]["details"][0]["field"] == "from"
    bad_band = client.get("/api/v1/analytics/heatmap", params={"amount_band": 99})
    assert bad_band.status_code == 422
    bad_bbox = client.get("/api/v1/analytics/heatmap", params={"bbox": "1,2,3"})
    assert bad_bbox.status_code == 422 and bad_bbox.json()["error"]["code"] == "GEO_BBOX_INVALID"


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------


def test_a_district_officer_sees_only_their_district(golden: TestClient) -> None:
    _login(golden, "district_officer")  # scope: demo-state-1 / demo-district-1

    loc = _by_id(_map(golden, layer="live", level="location"))
    assert set(loc) == {"loc-1", "loc-2"}  # not loc-4 (d-other) nor loc-5 (d-far)
    assert loc["loc-1"] == (pytest.approx(0.35), 2)

    cell = _map(golden, layer="live", level="cell")
    assert _by_id(cell) == {"cell-1": (pytest.approx(0.50), 3)}
    assert cell["suppressed_count"] == 0  # cell-3 and cell-4 are not even counted for them

    forbidden = golden.get("/api/v1/analytics/heatmap", params={"district": "d-other"})
    assert forbidden.status_code == 403 and forbidden.json()["error"]["code"] == "FORBIDDEN_SCOPE"
    ts = golden.get("/api/v1/analytics/timeseries").json()["points"]
    assert sum(p["alert_count"] for p in ts) == 3


def test_a_state_investigator_is_limited_to_their_state(golden: TestClient) -> None:
    _login(golden, "state_investigator")  # scope: demo-state-1

    assert set(_by_id(_map(golden, layer="live", level="location"))) == {"loc-1", "loc-2", "loc-4"}
    assert golden.get("/api/v1/analytics/heatmap", params={"state": "st-2"}).status_code == 403


def test_a_bank_scope_sees_only_its_own_locations_and_only_at_location_level(
    golden: TestClient,
) -> None:
    _login(golden, "bank_nodal")  # scope: demo-bank-1 (loc-1, loc-3, loc-4)

    assert set(_by_id(_map(golden, layer="live", level="location"))) == {"loc-1", "loc-4"}
    coarse = golden.get("/api/v1/analytics/heatmap", params={"level": "cell"})
    assert coarse.status_code == 403  # a cell mixes in other banks' locations


def test_an_unauthenticated_request_is_401(client: TestClient) -> None:
    assert client.get("/api/v1/analytics/heatmap").status_code == 401


# ---------------------------------------------------------------------------
# ETag / 304, and heat.version
# ---------------------------------------------------------------------------


def test_repeated_identical_queries_return_304(golden: TestClient) -> None:
    first = golden.get("/api/v1/analytics/heatmap", params={"level": "location"})
    etag = first.headers["ETag"]
    assert first.status_code == 200 and etag

    again = golden.get(
        "/api/v1/analytics/heatmap", params={"level": "location"}, headers={"If-None-Match": etag}
    )
    assert again.status_code == 304 and again.content == b""
    assert again.headers["ETag"] == etag

    # a different filter is a different answer: same If-None-Match must NOT match
    other = golden.get(
        "/api/v1/analytics/heatmap",
        params={"level": "location", "category": "upi_phishing"},
        headers={"If-None-Match": etag},
    )
    assert other.status_code == 200 and other.headers["ETag"] != etag

    # new data bumps the version: the old ETag no longer matches
    _raise_alert(golden, _at(14, 5), _complaint_ids(golden)["c3"], "loc-3")
    golden.app.state.clock.advance_to(_at(14, 10))  # type: ignore[attr-defined]
    fresh = golden.get(
        "/api/v1/analytics/heatmap", params={"level": "location"}, headers={"If-None-Match": etag}
    )
    assert fresh.status_code == 200 and fresh.headers["ETag"] != etag


def test_heat_version_is_published_after_commit_and_not_on_rollback(client: TestClient) -> None:
    st = client.app.state  # type: ignore[attr-defined]
    events: list[tuple[str, dict]] = []
    st.sse_hub.publish = lambda e: events.append((e.name, e.data))  # type: ignore[method-assign]
    c = _complaint_ids(client)

    forecast = _forecast(c["c1"], _at(12, 10), 0.9, 0.5, [("cell-1", 1.0)], [("loc-1", 1.0)])
    with _uow(client) as uow:  # a unit of work that rolls back: nothing may be announced
        assert uow.session is not None
        SqlForecastRepo(uow.session).save(forecast)
        st.event_bus_factory(uow.session).publish(
            ForecastGenerated(
                event_id=new_id(),
                occurred_at=_at(12, 10),
                forecast_id=forecast.id,
                complaint_id=c["c1"],
            )
        )
        uow.rollback()
    assert [n for n, _ in events if n == "heat.version"] == []

    _publish_forecast(client, forecast)
    assert [d for n, d in events if n == "heat.version"] == [{"version": 1}]


def test_forecasts_and_alerts_leave_the_rollup_version_increasing(golden: TestClient) -> None:
    body = _map(golden, layer="live", level="location")
    # 3 ForecastGenerated + 5 AlertRaised projections, one version each
    assert body["version"] == 8


# ---------------------------------------------------------------------------
# /geo
# ---------------------------------------------------------------------------


def test_geo_regions_are_scoped(golden: TestClient) -> None:
    assert {r["id"] for r in golden.get("/api/v1/geo/regions").json()} == {
        "demo-state-1",
        "st-2",
        "demo-district-1",
        "d-other",
        "d-far",
    }
    _login(golden, "district_officer")
    assert {r["id"] for r in golden.get("/api/v1/geo/regions").json()} == {
        "demo-district-1",
        "demo-state-1",
    }


def test_geo_locations_filter_page_and_scope(golden: TestClient) -> None:
    ids = lambda r: [i["id"] for i in r.json()["items"]]  # noqa: E731

    assert ids(golden.get("/api/v1/geo/locations")) == ["loc-1", "loc-2", "loc-3", "loc-4", "loc-5"]
    assert ids(golden.get("/api/v1/geo/locations", params={"kind": "ATM"})) == [
        "loc-1",
        "loc-4",
        "loc-5",
    ]
    assert ids(golden.get("/api/v1/geo/locations", params={"bank_id": "bank-2"})) == [
        "loc-2",
        "loc-5",
    ]
    assert ids(golden.get("/api/v1/geo/locations", params={"bbox": "80.9,26.8,81.1,27.0"})) == [
        "loc-1",
        "loc-2",
        "loc-3",
    ]

    page = golden.get("/api/v1/geo/locations", params={"limit": 2}).json()
    assert [i["id"] for i in page["items"]] == ["loc-1", "loc-2"] and page["next_cursor"] == "loc-2"
    rest = golden.get("/api/v1/geo/locations", params={"limit": 2, "cursor": "loc-2"}).json()
    assert [i["id"] for i in rest["items"]] == ["loc-3", "loc-4"]

    assert golden.get("/api/v1/geo/locations", params={"bbox": "bad"}).status_code == 422

    _login(golden, "district_officer")
    assert ids(golden.get("/api/v1/geo/locations")) == ["loc-1", "loc-2", "loc-3"]
    _login(golden, "bank_nodal")
    # a requested bank can narrow, never widen: asking for another bank's locations gets nothing
    assert ids(golden.get("/api/v1/geo/locations", params={"bank_id": "bank-2"})) == [
        "loc-1",
        "loc-3",
        "loc-4",
    ]
    assert ids(golden.get("/api/v1/geo/locations")) == ["loc-1", "loc-3", "loc-4"]
