"""A11: hosted-demo protections and ops (DOC 2 §2.7 "Public exposure"; DOC 4 A11): metrics, the
control-gate rate limit, the stream cap, the demo-users flag, the nightly reset, and restoring the
clock after a restart. Nothing here may be needed for the product to work with them all off."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from integration.test_live_chain import complaint, hops, login, post, registry, rows
from nakabandi.main import create_app


@pytest.fixture
def make_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Callable[..., TestClient]]:
    """A factory so a test can set env first: make_client(NAKABANDI_X="1")."""
    monkeypatch.setenv("API_SERVICE_KEY", "test-only-service-key")
    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-at-least-32-bytes-long")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'ops.db'}")
    # Isolated, guaranteed-empty model store — see integration/conftest.py's client fixture.
    monkeypatch.setenv("NAKABANDI_MODEL_STORE_DIR", str(tmp_path / "models"))
    opened: list[TestClient] = []

    def make(**env: str) -> TestClient:
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        c = TestClient(create_app())
        c.__enter__()
        opened.append(c)
        return c

    yield make
    for c in reversed(opened):
        c.__exit__(None, None, None)


# ---------------------------------------------------------------------------
# /system/metrics
# ---------------------------------------------------------------------------


def test_metrics_are_for_operators_only(make_client) -> None:  # noqa: ANN001
    client = make_client()
    assert client.get("/api/v1/system/metrics").status_code == 401
    login(client, "i4c_analyst")
    assert client.get("/api/v1/system/metrics").status_code == 403  # no SIM_CONTROL
    login(client, "demo_operator")
    assert client.get("/api/v1/system/metrics").status_code == 200


def test_metrics_report_real_stage_latencies_rates_and_outbox_depth(make_client) -> None:  # noqa: ANN001
    client = make_client()
    idle = {}
    login(client, "admin")
    idle = client.get("/api/v1/system/metrics").json()
    assert idle["stages"] == {} and idle["events_per_second"] == 0.0

    post(client, "registry", registry())
    post(client, "complaints", complaint("c1", "a1", 10))
    post(client, "hops", hops("c1", "a1", "a2", 15, "h-c1"))
    m = client.get("/api/v1/system/metrics").json()

    assert {
        "graph.resolve",
        "graph.context_for",
        "forecast.generate",
        "interception.assess",
        "alerting.raise_or_merge",
        "pipeline.total",
    } <= set(m["stages"])
    total = m["stages"]["pipeline.total"]
    assert total["count"] == 2  # the complaint, and its refresh when the hops arrived
    assert 0 < total["p50_ms"] <= total["p95_ms"] <= total["max_ms"]
    parts = sum(m["stages"][s]["p50_ms"] for s in m["stages"] if s != "pipeline.total")
    assert parts <= total["p50_ms"] * 1.5  # the stages account for the chain, give or take
    assert m["events_per_second"] > 0 and m["complaints_per_second"] > 0
    assert m["http"]["count"] > 0
    # the alert notices the new alert queued are waiting (no bank is configured to take them)
    assert m["outbox"]["pending"] + m["outbox"]["failed"] + m["outbox"]["sent"] >= 1
    assert m["delivery_failures"] == m["outbox"]["failed"] + m["outbox"]["dead"]
    assert m["uptime_s"] >= 0 and m["streams"] == {"open": 0, "max": 0}


# ---------------------------------------------------------------------------
# Hosted-demo protections
# ---------------------------------------------------------------------------


def test_the_control_gate_is_rate_limited_when_configured(make_client) -> None:  # noqa: ANN001
    client = make_client(NAKABANDI_CONTROL_RATE_PER_MIN="2")
    login(client, "demo_operator")

    codes = [
        client.get("/api/v1/auth/check", params={"role": "demo_operator"}).status_code
        for _ in range(4)
    ]

    assert codes == [204, 204, 429, 429]


def test_the_control_gate_is_not_limited_by_default(make_client) -> None:  # noqa: ANN001
    client = make_client()
    login(client, "demo_operator")
    codes = {
        client.get("/api/v1/auth/check", params={"role": "demo_operator"}).status_code
        for _ in range(40)
    }
    assert codes == {204}


def test_hosted_mode_switches_the_protections_on_with_the_doc_numbers(make_client) -> None:  # noqa: ANN001
    client = make_client(NAKABANDI_HOSTED_DEMO="true")
    state = client.app.state  # type: ignore[attr-defined]

    assert state.stream_gate.max_streams == 25
    assert state.control_limiter.enabled
    assert state.auto_pause.enabled is False  # needs a simulator URL to talk to


def test_a_full_stream_gate_refuses_another_stream_with_retry_after(make_client) -> None:  # noqa: ANN001
    client = make_client(NAKABANDI_MAX_SSE_STREAMS="1")
    login(client, "i4c_analyst")
    gate = client.app.state.stream_gate  # type: ignore[attr-defined]
    assert gate.try_open()  # one viewer is already connected

    r = client.get("/api/v1/stream")

    assert r.status_code == 503 and r.headers["Retry-After"] == "30"
    assert gate.open_streams == 1  # the refused request did not take a slot


def test_demo_users_can_be_switched_off(make_client) -> None:  # noqa: ANN001
    on = make_client()
    assert on.get("/api/v1/auth/demo-users").status_code == 200

    off = make_client(NAKABANDI_DEMO_USERS_ENABLED="false")
    assert off.get("/api/v1/auth/demo-users").status_code == 404


# ---------------------------------------------------------------------------
# The nightly reset
# ---------------------------------------------------------------------------


def _reset_world(client: TestClient) -> None:
    post(client, "registry", registry())
    post(client, "complaints", complaint("z9", "z-acct", 10))  # a ref the seed file never uses


def test_the_reset_restores_the_seeded_world_and_drops_everything_since(make_client) -> None:  # noqa: ANN001
    client = make_client(NAKABANDI_SEED_FILE=str(Path("data/seed/mini_ingest.jsonl").resolve()))
    _reset_world(client)
    assert rows(client, "SELECT COUNT(*) FROM alerts")[0][0] >= 1
    assert rows(client, "SELECT COUNT(*) FROM forecasts")[0][0] >= 1
    state = client.app.state  # type: ignore[attr-defined]

    report = state.run_reset_now()

    assert report.seed_lines > 0 and report.accepted > 0 and report.rejected == 0
    # what came after the seed is gone ...
    assert rows(client, "SELECT COUNT(*) FROM alerts") == [(0,)]
    assert rows(client, "SELECT COUNT(*) FROM forecasts") == [(0,)]
    assert rows(client, "SELECT COUNT(*) FROM complaints WHERE external_ref = 'z9'") == [(0,)]
    # ... the seeded data is back (through the same intake use cases) ...
    assert rows(client, "SELECT COUNT(*) FROM complaints")[0][0] > 0
    assert rows(client, "SELECT COUNT(*) FROM locations")[0][0] > 0
    # ... the old world's in-memory state is gone (the clock is back at the seed's own end) ...
    assert state.clock.now().year == 2026  # back at the seed's own end, not the world's
    assert not state.maintenance.locked()
    # ... and the demo still works: users exist, login works
    login(client, "i4c_analyst")
    assert client.get("/api/v1/alerts").status_code == 200


def test_the_reset_lets_the_world_be_run_again(make_client) -> None:  # noqa: ANN001
    client = make_client(NAKABANDI_SEED_FILE=str(Path("data/seed/mini_ingest.jsonl").resolve()))
    _reset_world(client)
    client.app.state.run_reset_now()  # type: ignore[attr-defined]

    _reset_world(client)  # the same registry and complaint, on a clean database

    assert rows(client, "SELECT COUNT(*) FROM complaints WHERE external_ref = 'z9'") == [(1,)]
    login(client, "i4c_analyst")
    assert len(client.get("/api/v1/alerts", params={"view": "all"}).json()["items"]) >= 1


def test_the_reset_with_no_seed_file_still_leaves_a_working_empty_world(make_client) -> None:  # noqa: ANN001
    client = make_client(NAKABANDI_SEED_FILE="/nonexistent/seed.jsonl")
    _reset_world(client)

    report = client.app.state.run_reset_now()  # type: ignore[attr-defined]

    assert (report.seed_lines, report.accepted) == (0, 0)
    assert rows(client, "SELECT COUNT(*) FROM complaints") == [(0,)]
    login(client, "i4c_analyst")


# ---------------------------------------------------------------------------
# Restart: the clock is restored from what was ingested
# ---------------------------------------------------------------------------


def test_a_restart_restores_the_sim_clock_from_the_newest_ingested_batch(  # noqa: ANN201
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("API_SERVICE_KEY", "test-only-service-key")
    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-at-least-32-bytes-long")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'restart.db'}")
    monkeypatch.setenv("NAKABANDI_MODEL_STORE_DIR", str(tmp_path / "models"))

    with TestClient(create_app()) as first:
        post(first, "registry", registry())
        post(first, "complaints", complaint("c1", "a1", 10))
        before = first.app.state.clock.now()  # type: ignore[attr-defined]
    assert before.year == 2026

    with TestClient(create_app()) as second:  # "kill and restart": a brand-new process's state
        assert second.app.state.clock.now() == before  # type: ignore[attr-defined]
