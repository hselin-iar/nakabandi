"""A10 unit tests (DOC 3 M4 / S3 TESTING PLAN, Unit): outcome classification at window and grace
edges, seeded budget ranking, uncertainty ordering."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from nakabandi.alerting.domain.alert import Alert
from nakabandi.alerting.domain.budget import (
    exploration_draw,
    priority,
    queue_key,
    rank_and_cap,
    shift_index,
)
from nakabandi.alerting.domain.outcome import classify_outcome
from nakabandi.alerting.domain.uncertainty import order_review_queue, uncertainty
from nakabandi.shared import Policy
from nakabandi_contracts.enums import AlertStatus, LadderLevel, Severity

POLICY = Policy.load(Path(__file__).resolve().parents[4] / "config" / "policy.yaml")
T0 = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
WINDOW_END = T0 + timedelta(hours=1)
GRACE = timedelta(hours=POLICY.outcome.grace_hours)  # 6 h in policy.yaml


def _alert(
    alert_id: str = "a",
    *,
    confidence: float = 0.8,
    prio: float = 1.0,
    severity: Severity = Severity.HIGH,
    district: str | None = "d1",
    created_at: datetime = T0,
) -> Alert:
    return Alert(
        id=alert_id,
        cluster_ref="cl",
        target_kind="ATM",
        target_id="loc-1",
        target_name="ATM",
        dedup_key=f"cl:ATM:{alert_id}",
        severity=severity,
        confidence=confidence,
        status=AlertStatus.OPEN,
        ladder_level=LadderLevel.L1,
        is_deferred=False,
        is_probe=False,
        window_start=T0,
        window_end=WINDOW_END,
        expires_at=WINDOW_END + timedelta(minutes=15),
        created_at=created_at,
        forecast_id="f",
        complaint_id="c",
        priority=prio,
        scope_district_id=district,
    )


# ---------------------------------------------------------------------------
# Outcome classification: window and grace edges
# ---------------------------------------------------------------------------


def _classify(observation_at: datetime | None):  # noqa: ANN202
    return classify_outcome(_alert(), observation_at, WINDOW_END + GRACE, "obs", POLICY, "o1")


@pytest.mark.parametrize(
    ("observation_at", "expected"),
    [
        (T0 - timedelta(seconds=1), None),  # before the window opens: says nothing
        (T0, "hit"),  # the window is closed on both ends
        (T0 + timedelta(minutes=30), "hit"),
        (WINDOW_END, "hit"),
        (WINDOW_END + timedelta(seconds=1), "late"),
        (WINDOW_END + GRACE, "late"),  # the grace period is inclusive
        (WINDOW_END + GRACE + timedelta(seconds=1), None),  # beyond grace: ignored
    ],
)
def test_observation_outcome_at_the_window_and_grace_edges(
    observation_at: datetime, expected: str | None
) -> None:
    outcome = _classify(observation_at)
    assert (outcome.result if outcome else None) == expected


def test_no_observation_is_a_miss_decided_by_the_timer() -> None:
    outcome = _classify(None)
    assert outcome is not None and outcome.result == "miss" and outcome.observation_id is None


def test_a_hit_carries_its_observation_and_is_a_reconciled_outcome() -> None:
    outcome = _classify(T0 + timedelta(minutes=5))
    assert outcome is not None
    assert (outcome.observation_id, outcome.source, outcome.actor_id) == ("obs", "reconciled", None)


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


def test_priority_is_confidence_times_log1p_amount_times_interception_probability() -> None:
    import math

    assert priority(0.5, 1_000_000, 0.4) == pytest.approx(0.5 * math.log1p(1_000_000) * 0.4)
    assert priority(0.9, -5, 1.0) == 0.0  # a negative amount cannot raise priority


def test_shift_index_changes_every_policy_shift_hours() -> None:
    shift = timedelta(hours=POLICY.alerting.shift_hours)
    assert shift_index(T0, POLICY) == shift_index(T0 + timedelta(minutes=1), POLICY)
    assert shift_index(T0 + shift, POLICY) == shift_index(T0, POLICY) + 1


def test_queue_key_is_district_and_shift_and_unscoped_when_unknown() -> None:
    assert queue_key(_alert(district="d7"), POLICY) == ("d7", shift_index(T0, POLICY))
    assert queue_key(_alert(district=None), POLICY)[0] == "unscoped"


def _with_budget(cap: int, share: float) -> Policy:
    alerting = POLICY.alerting.model_copy(
        update={"budget_per_shift": cap, "exploration_share": share}
    )
    return POLICY.model_copy(update={"alerting": alerting})


def test_the_top_n_by_priority_are_visible_and_the_rest_deferred() -> None:
    alerts = [_alert(f"a{i}", prio=float(i)) for i in range(10)]

    ranked = rank_and_cap(alerts, _with_budget(cap=4, share=0.0))

    assert [a.id for a in ranked[:4]] == ["a9", "a8", "a7", "a6"]
    assert [a.budget_rank for a in ranked] == list(range(1, 11))
    assert [a.is_deferred for a in ranked] == [False] * 4 + [True] * 6
    assert not any(a.is_probe for a in ranked)


def test_ties_break_by_age_then_id() -> None:
    older = _alert("z", prio=1.0, created_at=T0)
    newer = _alert("a", prio=1.0, created_at=T0 + timedelta(minutes=1))
    same_age_lower_id = _alert("b", prio=1.0, created_at=T0)

    ranked = rank_and_cap([newer, older, same_age_lower_id], _with_budget(cap=10, share=0.0))

    assert [a.id for a in ranked] == ["b", "z", "a"]


def test_exploration_promotes_a_deferred_alert_to_a_probe_not_deferred() -> None:
    alerts = [_alert(f"a{i}", prio=float(i)) for i in range(6)]

    rank_and_cap(alerts, _with_budget(cap=2, share=1.0))  # share 1: every deferred one is a probe

    beyond_cap = [a for a in alerts if a.budget_rank and a.budget_rank > 2]
    assert beyond_cap and all(a.is_probe and not a.is_deferred for a in beyond_cap)


def test_the_same_ids_give_the_same_exploration_picks_whatever_the_input_order() -> None:
    policy = _with_budget(cap=5, share=0.3)

    def picks(order: list[int]) -> set[str]:
        alerts = [_alert(f"id-{i:03d}", prio=float(i)) for i in order]
        rank_and_cap(alerts, policy)
        return {a.id for a in alerts if a.is_probe}

    forward = picks(list(range(60)))
    assert forward == picks(list(reversed(range(60))))
    assert forward == picks(list(range(60)))  # and across runs
    assert 0 < len(forward) < 55  # a real mix of probes and deferred


def test_the_seed_changes_the_draw_but_the_draw_is_stable() -> None:
    assert exploration_draw("x", "s1") == exploration_draw("x", "s1")
    assert 0.0 <= exploration_draw("x") < 1.0
    assert exploration_draw("x", "s1") != exploration_draw("x", "s2")


def test_probe_share_tracks_exploration_share_over_many_alerts() -> None:
    alerts = [_alert(f"id-{i:05d}", prio=1.0 / (i + 1)) for i in range(4000)]
    rank_and_cap(alerts, _with_budget(cap=0, share=0.05))
    probes = sum(a.is_probe for a in alerts)
    assert 120 < probes < 280  # 5% of 4000 = 200, well inside sampling noise


# ---------------------------------------------------------------------------
# Uncertainty and the review queue
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("confidence", "expected"), [(0.0, 0.0), (0.25, 0.5), (0.5, 1.0), (0.75, 0.5), (1.0, 0.0)]
)
def test_uncertainty_is_highest_at_one_half(confidence: float, expected: float) -> None:
    assert uncertainty(confidence) == pytest.approx(expected)


def test_review_queue_is_most_uncertain_first_then_severity_then_age() -> None:
    a = _alert("a", confidence=0.95)
    b = _alert("b", confidence=0.50)
    c = _alert("c", confidence=0.70)
    d = _alert("d", confidence=0.30, severity=Severity.CRITICAL)  # ties with c at 0.6 uncertainty
    e = _alert("e", confidence=0.70, severity=Severity.LOW, created_at=T0 - timedelta(hours=1))

    ordered = order_review_queue([a, c, d, e, b])

    assert [x.id for x in ordered] == ["b", "d", "c", "e", "a"]


# ---------------------------------------------------------------------------
# Severity bands are calibrated to the score's real range (they were once 0.8 / 0.6 / 0.35, which
# made every alert with a real amount CRITICAL)
# ---------------------------------------------------------------------------


def test_severity_bands_spread_realistic_alerts_across_all_four_levels() -> None:
    from collections import Counter

    from nakabandi.alerting.domain.severity import severity
    from nakabandi_contracts.enums import Verdict

    grid = [
        severity(confidence, amount_paise, verdict, POLICY)
        for confidence in (0.3, 0.5, 0.7, 0.9)
        for amount_paise in (1_000_000, 10_000_000, 100_000_000)  # INR 10k, 1 lakh, 10 lakh
        for verdict in (Verdict.MARGINAL, Verdict.INTERCEPTABLE)
    ]
    counts = Counter(grid)

    assert set(counts) == {Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL}
    assert counts[Severity.CRITICAL] < len(grid) / 2  # not "everything is critical" again


def test_severity_rises_with_confidence_amount_and_interceptability() -> None:
    from nakabandi.alerting.domain.severity import severity
    from nakabandi_contracts.enums import Verdict

    order = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]

    def rank(c: float, a: int, v: Verdict) -> int:
        return order.index(severity(c, a, v, POLICY))

    assert rank(0.9, 10**7, Verdict.INTERCEPTABLE) >= rank(0.3, 10**7, Verdict.INTERCEPTABLE)
    assert rank(0.6, 10**8, Verdict.INTERCEPTABLE) >= rank(0.6, 10**6, Verdict.INTERCEPTABLE)
    assert rank(0.6, 10**7, Verdict.INTERCEPTABLE) >= rank(0.6, 10**7, Verdict.MARGINAL)


# ---------------------------------------------------------------------------
# Bank callbacks at the SAME sim time (found in the Sync 5 joint run)
# ---------------------------------------------------------------------------


def _hold_action(at: datetime = T0):  # noqa: ANN202
    from nakabandi.alerting.domain.action import Action, ActionStatus
    from nakabandi_contracts.enums import ActionType

    return Action(
        id="a1",
        alert_id="al",
        type=ActionType.REQUEST_HOLD,
        actor_user_id="u",
        actor_role="i4c_analyst",
        reason=None,
        params={},
        status=ActionStatus.PENDING,
        at=at,
        status_at=at,
    )


def test_a_first_callback_at_the_creation_sim_time_is_accepted() -> None:
    """bank-sim's fallback sim time is the latest webhook's: the moment the hold was created."""
    from nakabandi.alerting.domain.action import ActionStatus

    action = _hold_action()

    assert action.apply_callback(ActionStatus.APPLIED, T0, 1_400_000, None) is True
    assert (action.status, action.applied_amount_paise) == (ActionStatus.APPLIED, 1_400_000)


def test_apply_then_release_at_one_sim_time_are_both_accepted_in_that_order() -> None:
    from nakabandi.alerting.domain.action import ActionStatus

    action = _hold_action()

    assert action.apply_callback(ActionStatus.APPLIED, T0, 1_000, None)
    assert action.apply_callback(ActionStatus.RELEASED, T0, None, None)
    assert action.status is ActionStatus.RELEASED


def test_at_one_sim_time_a_step_backwards_or_a_duplicate_is_ignored() -> None:
    from nakabandi.alerting.domain.action import ActionStatus

    action = _hold_action()
    action.apply_callback(ActionStatus.APPLIED, T0, 1_000, None)
    action.apply_callback(ActionStatus.RELEASED, T0, None, None)

    assert action.apply_callback(ActionStatus.APPLIED, T0, 1_000, None) is False  # backwards
    assert action.apply_callback(ActionStatus.RELEASED, T0, None, None) is False  # duplicate
    assert action.status is ActionStatus.RELEASED


def test_an_older_callback_is_still_ignored_whatever_its_status() -> None:
    from nakabandi.alerting.domain.action import ActionStatus

    action = _hold_action(T0 + timedelta(hours=2))

    assert action.apply_callback(ActionStatus.RELEASED, T0, None, None) is False
    assert action.status is ActionStatus.PENDING
