"""A10 Done When (DOC 4 Step A10): outcome classification is correct at window and grace edges
(unit tests, plus the end-to-end paths here); the same seed gives the same exploration picks
(unit); deferred alerts remain reachable under Backlog; officer feedback (MarkOutcome).

The confirmed-hit path is proven here down to graph's affinity table, and against the real chain in
tests/integration/test_live_chain.py (a confirmed hit changes the next forecast).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from nakabandi.alerting import AlertService
from nakabandi.alerting.infrastructure.models import AlertModel, OutcomeModel
from nakabandi.audit.infrastructure.models import AuditEntryModel
from nakabandi.geo import LocationScope, LocationScopeLookup
from nakabandi.intake import LienContextLookup
from nakabandi.shared import OutcomeRecorded

from alerting.test_actions_outbox import (
    DEMO_SCOPE,
    SERVICE_HEADERS,
    FixedScope,
    _complaint_id,
    _login,
    _new_alert,
    _rows,
    _uow,
)
from alerting.test_use_cases import FakeAssessment, FakeForecast, FakeTarget

GRACE_H = 6  # policy.yaml outcome.grace_hours


def _alert_window(client: TestClient, alert_id: str) -> tuple[datetime, datetime]:
    _login(client, "i4c_analyst")
    a = client.get(f"/api/v1/alerts/{alert_id}").json()
    return datetime.fromisoformat(a["window_start"]), datetime.fromisoformat(a["window_end"])


def _observe(client: TestClient, location_id: str, event_at: datetime, key: str) -> dict:
    """Ingest one cash-out through the real ingest API (which publishes ObservationIngested)."""
    body = {
        "batch_id": key,
        "idempotency_key": key,
        "sim_time": event_at.isoformat(),
        "items": [
            {
                "account_ref": "acc-5",
                "location_id": location_id,
                "channel": "ATM",
                "amount_paise": 1000,
                "event_at": event_at.isoformat(),
                "observed_at": event_at.isoformat(),
                "source": "bank_report",
            }
        ],
    }
    r = client.post("/api/v1/ingest/cashout-observations", json=body, headers=SERVICE_HEADERS)
    assert r.status_code == 200 and r.json()["accepted"] == 1, r.text
    return r.json()


def _outcomes(client: TestClient, alert_id: str) -> list[tuple[str, str]]:
    return sorted(
        (o.result, o.source) for o in _rows(client, OutcomeModel) if o.alert_id == alert_id
    )


def _timeline(client: TestClient, alert_id: str) -> list[str]:
    _login(client, "i4c_analyst")
    return [t["text_code"] for t in client.get(f"/api/v1/alerts/{alert_id}").json()["timeline"]]


def _graph_stats(client: TestClient, cluster_id: str) -> list[tuple[str, int]]:
    """The cluster's cash-out affinity as graph holds it: (location, observations)."""
    from datetime import UTC

    from nakabandi.graph.infrastructure.repositories import SqlClusterRepo

    with _uow(client) as uow:
        assert uow.session is not None
        stats = SqlClusterRepo(uow.session).get_location_stats(
            cluster_id, datetime(2100, 1, 1, tzinfo=UTC)
        )
    return sorted((s.location_id, s.observation_count) for s in stats)


def _advance_to(client: TestClient, t: datetime) -> None:
    client.app.state.clock.advance_to(t)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# ReconcileOutcome: data-driven hit / late
# ---------------------------------------------------------------------------


def test_a_cash_out_inside_the_window_is_a_reconciled_hit(client: TestClient) -> None:
    alert_id = _new_alert(client, "loc-1")
    start, end = _alert_window(client, alert_id)

    _observe(client, "loc-1", start + (end - start) / 2, "obs-hit")

    assert _outcomes(client, alert_id) == [("hit", "reconciled")]
    assert "alert.outcome.hit" in _timeline(client, alert_id)


def test_a_cash_out_after_the_window_but_within_grace_is_late(client: TestClient) -> None:
    alert_id = _new_alert(client, "loc-1")
    _, end = _alert_window(client, alert_id)

    _observe(client, "loc-1", end + timedelta(minutes=30), "obs-late")

    assert _outcomes(client, alert_id) == [("late", "reconciled")]


def test_a_cash_out_beyond_grace_or_elsewhere_decides_nothing(client: TestClient) -> None:
    alert_id = _new_alert(client, "loc-1")
    _, end = _alert_window(client, alert_id)

    _observe(client, "loc-1", end + timedelta(hours=GRACE_H, seconds=1), "obs-too-late")
    _observe(client, "loc-2", end - timedelta(minutes=5), "obs-elsewhere")

    assert _outcomes(client, alert_id) == []


def test_an_alert_gets_one_reconciled_outcome(client: TestClient) -> None:
    alert_id = _new_alert(client, "loc-1")
    start, end = _alert_window(client, alert_id)

    _observe(client, "loc-1", start + timedelta(minutes=5), "obs-1")
    _observe(client, "loc-1", start + timedelta(minutes=10), "obs-2")

    assert _outcomes(client, alert_id) == [("hit", "reconciled")]


def test_an_observation_is_matched_only_to_alerts_at_its_own_location(client: TestClient) -> None:
    a1 = _new_alert(client, "loc-1")
    a2 = _new_alert(client, "loc-2")
    start, _ = _alert_window(client, a1)

    _observe(client, "loc-2", start + timedelta(minutes=5), "obs-loc2")

    assert _outcomes(client, a1) == [] and _outcomes(client, a2) == [("hit", "reconciled")]


def test_outcome_recorded_is_published_on_the_bus(client: TestClient) -> None:
    seen: list[OutcomeRecorded] = []
    client.app.state.bus_registrars.append(  # type: ignore[attr-defined]
        lambda bus, _s: bus.subscribe(OutcomeRecorded, lambda e: seen.append(e))
    )
    alert_id = _new_alert(client, "loc-1")
    start, _ = _alert_window(client, alert_id)

    _observe(client, "loc-1", start + timedelta(minutes=5), "obs-evt")

    assert [(e.alert_id, e.result) for e in seen] == [(alert_id, "hit")]


# ---------------------------------------------------------------------------
# ReconcileOutcome: timer-driven miss
# ---------------------------------------------------------------------------


def test_a_miss_is_decided_by_the_timer_and_only_after_window_plus_grace(
    client: TestClient,
) -> None:
    alert_id = _new_alert(client, "loc-1")
    _, end = _alert_window(client, alert_id)
    run = client.app.state.run_timers_once  # type: ignore[attr-defined]

    _advance_to(client, end + timedelta(hours=GRACE_H) - timedelta(minutes=1))
    run()
    assert _outcomes(client, alert_id) == []  # window passed, grace not yet: nothing decided

    _advance_to(client, end + timedelta(hours=GRACE_H, minutes=1))
    run()
    assert _outcomes(client, alert_id) == [("miss", "reconciled")]
    run()
    assert _outcomes(client, alert_id) == [("miss", "reconciled")]  # and only once


def test_data_arriving_never_decides_a_miss(client: TestClient) -> None:
    alert_id = _new_alert(client, "loc-1")
    _, end = _alert_window(client, alert_id)

    # Long after window + grace, an unrelated cash-out arrives (event_at far too late to count).
    _observe(client, "loc-1", end + timedelta(hours=GRACE_H + 3), "obs-way-late")

    assert _outcomes(client, alert_id) == []  # only the timer may call a miss


def test_a_hit_before_the_deadline_prevents_the_miss(client: TestClient) -> None:
    alert_id = _new_alert(client, "loc-1")
    start, end = _alert_window(client, alert_id)
    _observe(client, "loc-1", start + timedelta(minutes=5), "obs-early")

    _advance_to(client, end + timedelta(hours=GRACE_H, minutes=5))
    client.app.state.run_timers_once()  # type: ignore[attr-defined]

    assert _outcomes(client, alert_id) == [("hit", "reconciled")]


def test_an_expired_alert_still_gets_its_miss(client: TestClient) -> None:
    alert_id = _new_alert(client, "loc-1")
    _, end = _alert_window(client, alert_id)
    run = client.app.state.run_timers_once  # type: ignore[attr-defined]

    _advance_to(client, end + timedelta(hours=1))
    run()  # escalates, then expires the unattended alert
    _login(client, "i4c_analyst")
    assert client.get(f"/api/v1/alerts/{alert_id}").json()["status"] == "expired"

    _advance_to(client, end + timedelta(hours=GRACE_H, minutes=1))
    run()
    assert _outcomes(client, alert_id) == [("miss", "reconciled")]


# ---------------------------------------------------------------------------
# MarkOutcome (the officer)
# ---------------------------------------------------------------------------


def _mark(client: TestClient, alert_id: str, **body: object):  # noqa: ANN202
    return client.post(f"/api/v1/alerts/{alert_id}/outcome", json=body)


def test_an_officer_marks_a_hit_with_a_location_and_the_graph_is_told(client: TestClient) -> None:
    alert_id = _new_alert(client, "loc-1")
    _login(client, "state_investigator")
    assert client.post(f"/api/v1/alerts/{alert_id}/acknowledge").status_code == 200

    r = _mark(client, alert_id, result="hit", location_id="loc-2", reason="seen on CCTV")

    assert r.status_code == 201, r.text
    body = r.json()
    assert (body["result"], body["source"], body["alert_id"]) == ("hit", "officer", alert_id)
    assert _outcomes(client, alert_id) == [("hit", "officer")]
    # the officer's confirmed location is now part of the cluster's affinity in graph
    assert _graph_stats(client, "cluster-1") == [("loc-2", 1)]
    # audited, and the worked alert is closed
    assert any(a.action == "outcome.marked" for a in _rows(client, AuditEntryModel))
    assert client.get(f"/api/v1/alerts/{alert_id}").json()["status"] == "closed"


def test_a_repeated_mark_is_idempotent(client: TestClient) -> None:
    alert_id = _new_alert(client, "loc-1")
    _login(client, "state_investigator")

    first = _mark(client, alert_id, result="hit", location_id="loc-2")
    again = _mark(client, alert_id, result="hit", location_id="loc-2")
    other = _mark(client, alert_id, result="miss")

    assert (first.status_code, again.status_code, other.status_code) == (201, 200, 201)
    assert again.json()["id"] == first.json()["id"]
    assert len(_outcomes(client, alert_id)) == 2  # the repeat added no row
    assert _graph_stats(client, "cluster-1") == [("loc-2", 1)]  # the repeat did not count twice


def test_bank_nodal_cannot_mark_an_outcome(client: TestClient) -> None:
    alert_id = _new_alert(client, "loc-1")
    _login(client, "bank_nodal")

    r = _mark(client, alert_id, result="hit")

    assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN_PERMISSION"
    assert _outcomes(client, alert_id) == []


def test_an_officer_cannot_mark_an_alert_outside_their_scope(client: TestClient) -> None:
    elsewhere = LocationScope(state_id="other-state", district_id="d", bank_id="bank-1")
    alert_id = _new_alert(client, "loc-1", scope=elsewhere)
    _login(client, "state_investigator")  # scope: demo-state-1

    r = _mark(client, alert_id, result="hit")

    assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN_SCOPE"


def test_a_location_outside_the_registry_is_a_422(client: TestClient) -> None:
    alert_id = _new_alert(client, "loc-1")
    _login(client, "state_investigator")

    r = _mark(client, alert_id, result="hit", location_id="not-a-location")

    assert r.status_code == 422 and r.json()["error"]["code"] == "OUTCOME_LOCATION_UNKNOWN"
    assert _outcomes(client, alert_id) == []
    assert _graph_stats(client, "cluster-1") == []


def test_invalid_results_and_a_location_on_a_miss_are_422(client: TestClient) -> None:
    alert_id = _new_alert(client, "loc-1")
    _login(client, "state_investigator")

    assert _mark(client, alert_id, result="maybe").json()["error"]["code"] == "OUTCOME_INVALID"
    on_miss = _mark(client, alert_id, result="miss", location_id="loc-2")
    assert on_miss.status_code == 422 and on_miss.json()["error"]["code"] == "OUTCOME_INVALID"


def test_feedback_on_an_expired_alert_is_recorded_and_does_not_reopen_it(
    client: TestClient,
) -> None:
    alert_id = _new_alert(client, "loc-1")
    _, end = _alert_window(client, alert_id)
    _advance_to(client, end + timedelta(hours=1))
    client.app.state.run_timers_once()  # type: ignore[attr-defined]
    _login(client, "state_investigator")

    r = _mark(client, alert_id, result="hit", location_id="loc-2")

    assert r.status_code == 201
    assert client.get(f"/api/v1/alerts/{alert_id}").json()["status"] == "expired"


def test_the_alert_shows_both_an_officer_and_a_reconciled_outcome(client: TestClient) -> None:
    alert_id = _new_alert(client, "loc-1")
    start, _ = _alert_window(client, alert_id)
    _observe(client, "loc-1", start + timedelta(minutes=5), "obs-both")  # reconciled: hit
    _login(client, "state_investigator")
    _mark(client, alert_id, result="miss", reason="patrol found nothing")  # the officer disagrees

    detail = client.get(f"/api/v1/alerts/{alert_id}").json()

    assert sorted((o["result"], o["source"]) for o in detail["outcomes"]) == [
        ("hit", "reconciled"),
        ("miss", "officer"),
    ]
    assert set(detail["outcomes"][0]) == {"id", "alert_id", "result", "source", "at"}  # LC-4


# ---------------------------------------------------------------------------
# Review queue
# ---------------------------------------------------------------------------


def _raise(
    client: TestClient, confidence: float, target: str, policy=None, scope=DEMO_SCOPE
) -> str:  # noqa: ANN001
    st = client.app.state  # type: ignore[attr-defined]
    with _uow(client) as uow:
        assert uow.session is not None
        svc = AlertService(
            session=uow.session,
            clock=st.clock,
            policy=policy or st.policy,
            role_permissions=st.role_permissions,
            sse_hub=st.sse_hub,
            scope_lookup=FixedScope(scope),
            bus=st.event_bus_factory(uow.session),
        )
        result = svc.raise_or_merge(
            FakeForecast(id=f"f-{target}"),
            [FakeAssessment(confidence=confidence, target=FakeTarget(id=target))],
        )
        uow.commit()
    assert result.alert_id is not None
    return result.alert_id


def test_the_review_queue_is_most_uncertain_first_and_drops_labelled_alerts(
    client: TestClient,
) -> None:
    sure = _raise(client, 0.95, "loc-a")
    unsure = _raise(client, 0.50, "loc-b")
    middling = _raise(client, 0.70, "loc-c")
    _login(client, "state_investigator")

    def queue() -> list[str]:
        return [
            a["id"] for a in client.get("/api/v1/alerts", params={"view": "review"}).json()["items"]
        ]

    assert queue() == [unsure, middling, sure]

    assert _mark(client, unsure, result="miss").status_code == 201
    assert queue() == [middling, sure]  # once labelled, an alert leaves the queue


def test_the_review_queue_respects_scope(client: TestClient) -> None:
    mine = _raise(client, 0.5, "loc-a")
    elsewhere = LocationScope(state_id="other-state", district_id="d", bank_id="bank-1")
    _raise(client, 0.5, "loc-b", scope=elsewhere)
    _login(client, "state_investigator")

    ids = [a["id"] for a in client.get("/api/v1/alerts", params={"view": "review"}).json()["items"]]

    assert ids == [mine]


# ---------------------------------------------------------------------------
# Budget: per (jurisdiction, shift), deferred alerts stay reachable under Backlog
# ---------------------------------------------------------------------------


def _policy(client: TestClient, cap: int, share: float):  # noqa: ANN202
    policy = client.app.state.policy  # type: ignore[attr-defined]
    alerting = policy.alerting.model_copy(
        update={"budget_per_shift": cap, "exploration_share": share}
    )
    return policy.model_copy(update={"alerting": alerting})


def _ids(client: TestClient, **params: object) -> list[str]:
    r = client.get("/api/v1/alerts", params={"limit": 200, **params})
    assert r.status_code == 200, r.text
    return [a["id"] for a in r.json()["items"]]


def test_alerts_beyond_the_shift_budget_are_deferred_but_reachable_under_backlog(
    client: TestClient,
) -> None:
    policy = _policy(client, cap=3, share=0.0)
    confidences = [0.9, 0.8, 0.7, 0.6, 0.5]  # priority follows confidence (same amount)
    ids = [_raise(client, c, f"loc-{i}", policy) for i, c in enumerate(confidences)]
    _login(client, "i4c_analyst")

    assert set(_ids(client)) == set(ids[:3])  # the queue: the top 3
    assert set(_ids(client, view="backlog")) == set(ids[3:])  # the rest are not lost
    assert set(_ids(client, view="all")) == set(ids)
    ranks = {a: client.get(f"/api/v1/alerts/{a}").json() for a in ids}
    with _uow(client) as uow:
        assert uow.session is not None
        rows = {r.id: r for r in uow.session.query(AlertModel).all()}
    assert [rows[i].budget_rank for i in ids] == [1, 2, 3, 4, 5]
    assert [rows[i].is_deferred for i in ids] == [False, False, False, True, True]
    assert all(ranks[a]["is_deferred"] == rows[a].is_deferred for a in ids)


def test_a_higher_priority_alert_arriving_later_pushes_the_lowest_into_the_backlog(
    client: TestClient,
) -> None:
    policy = _policy(client, cap=2, share=0.0)
    low = _raise(client, 0.5, "loc-1", policy)
    mid = _raise(client, 0.6, "loc-2", policy)
    _login(client, "i4c_analyst")
    assert set(_ids(client)) == {low, mid}

    high = _raise(client, 0.9, "loc-3", policy)

    _login(client, "i4c_analyst")
    assert set(_ids(client)) == {mid, high}
    assert _ids(client, view="backlog") == [low]  # ranked again, the older alert dropped a place


def test_each_district_has_its_own_budget(client: TestClient) -> None:
    policy = _policy(client, cap=2, share=0.0)
    d1 = LocationScope(state_id="demo-state-1", district_id="district-1", bank_id="b")
    d2 = LocationScope(state_id="demo-state-1", district_id="district-2", bank_id="b")
    a = [_raise(client, 0.9 - i / 10, f"a-{i}", policy, scope=d1) for i in range(2)]
    b = [_raise(client, 0.9 - i / 10, f"b-{i}", policy, scope=d2) for i in range(2)]
    _login(client, "i4c_analyst")

    assert _ids(client, view="backlog") == []  # two per district fit two-per-district budgets
    _raise(client, 0.3, "a-extra", policy, scope=d1)  # above the 0.2 alert floor, lowest priority
    assert len(_ids(client, view="backlog")) == 1  # only district-1 overflowed
    assert set(_ids(client)) == set(a + b)


def test_exploration_promotes_deferred_alerts_to_probes_that_stay_in_the_queue(
    client: TestClient,
) -> None:
    policy = _policy(client, cap=1, share=1.0)  # every deferred alert becomes a probe
    ids = [_raise(client, 0.9 - i / 10, f"loc-{i}", policy) for i in range(3)]
    _login(client, "i4c_analyst")

    assert set(_ids(client)) == set(ids) and _ids(client, view="backlog") == []
    probes = [a["is_probe"] for a in (client.get(f"/api/v1/alerts/{i}").json() for i in ids)]
    assert probes == [False, True, True]  # the top one is ordinary; the ones beyond cap are probes


def test_priority_uses_the_complaints_amount_when_the_forecast_has_none(
    client: TestClient,
) -> None:
    """A real Forecast carries no amount, so severity and priority were computed from 0 (always
    LOW) until the amount was looked up through intake."""

    class ForecastWithoutAmount:
        def __init__(self, complaint_id: str) -> None:
            self.id, self.complaint_id, self.cluster_id = "f-x", complaint_id, "cluster-x"

    st = client.app.state  # type: ignore[attr-defined]
    complaint_id = _complaint_id(client, "c1")  # 500_000 paise

    def raise_with(lien_context) -> str:  # noqa: ANN001
        with _uow(client) as uow:
            assert uow.session is not None
            result = AlertService(
                session=uow.session,
                clock=st.clock,
                policy=st.policy,
                role_permissions=st.role_permissions,
                sse_hub=st.sse_hub,
                scope_lookup=LocationScopeLookup(uow.session),
                lien_context=lien_context(uow.session) if lien_context else None,
                bus=st.event_bus_factory(uow.session),
            ).raise_or_merge(
                ForecastWithoutAmount(complaint_id),
                [FakeAssessment(target=FakeTarget(id=f"loc-{lien_context is None}"))],
            )
            uow.commit()
        assert result.alert_id is not None
        return result.alert_id

    without = raise_with(None)
    with_amount = raise_with(LienContextLookup)
    with _uow(client) as uow:
        assert uow.session is not None
        rows = {r.id: r for r in uow.session.query(AlertModel).all()}
    assert (rows[without].severity, rows[without].priority) == ("LOW", 0.0)
    assert rows[with_amount].severity != "LOW" and rows[with_amount].priority > 0
    assert rows[with_amount].priority == pytest.approx(0.75 * 13.122363 * 0.3, rel=1e-3)
