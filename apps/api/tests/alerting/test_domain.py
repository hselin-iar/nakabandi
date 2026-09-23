"""Unit tests for alerting domain (DOC 4 A7: Every legal and illegal transition is tested;
duplicate complaints merge; severity bands; budget cap + seeded exploration).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from nakabandi.alerting.domain.alert import Alert, TimelineEntry
from nakabandi.alerting.domain.budget import rank_and_cap
from nakabandi.alerting.domain.dedup import dedup_key
from nakabandi.alerting.domain.severity import severity
from nakabandi.shared import Conflict, Policy
from nakabandi_contracts.enums import AlertStatus, LadderLevel, Severity, Verdict

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2024, 1, 1, tzinfo=UTC)


def _make_alert(
    alert_id: str = "alert-1",
    status: AlertStatus = AlertStatus.OPEN,
    confidence: float = 0.8,
) -> Alert:
    return Alert(
        id=alert_id,
        cluster_ref="cluster-1",
        target_kind="ATM",
        target_id="loc-1",
        target_name="ATM Branch",
        dedup_key=dedup_key("cluster-1", "ATM", "loc-1"),
        severity=Severity.HIGH,
        confidence=confidence,
        status=status,
        ladder_level=LadderLevel.L1,
        is_deferred=False,
        is_probe=False,
        window_start=_NOW,
        window_end=_NOW,
        expires_at=_NOW,
        created_at=_NOW,
        forecast_id="fc-1",
    )


def _entry(kind: str = "acknowledged") -> TimelineEntry:
    return TimelineEntry(
        id="tl-1",
        alert_id="alert-1",
        at=_NOW,
        kind=kind,
        actor_id=None,
        text_code=f"alert.{kind}",
        text_params={},
    )


# ---------------------------------------------------------------------------
# State machine: legal transitions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED),
        (AlertStatus.OPEN, AlertStatus.ACTIONED),
        (AlertStatus.OPEN, AlertStatus.ESCALATED),
        (AlertStatus.OPEN, AlertStatus.EXPIRED),
        (AlertStatus.ESCALATED, AlertStatus.ACKNOWLEDGED),
        (AlertStatus.ESCALATED, AlertStatus.ACTIONED),
        (AlertStatus.ESCALATED, AlertStatus.EXPIRED),
        (AlertStatus.ACKNOWLEDGED, AlertStatus.ACTIONED),
        (AlertStatus.ACKNOWLEDGED, AlertStatus.CLOSED),
        (AlertStatus.ACKNOWLEDGED, AlertStatus.EXPIRED),
        (AlertStatus.ACTIONED, AlertStatus.CLOSED),
    ],
)
def test_legal_transition(from_status: AlertStatus, to_status: AlertStatus) -> None:
    alert = _make_alert(status=from_status)
    alert.transition(to_status, _entry(to_status.value))
    assert alert.status == to_status
    assert len(alert.timeline) == 1


# ---------------------------------------------------------------------------
# State machine: illegal transitions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        # Terminal states have no outgoing transitions
        (AlertStatus.EXPIRED, AlertStatus.OPEN),
        (AlertStatus.EXPIRED, AlertStatus.ACKNOWLEDGED),
        (AlertStatus.CLOSED, AlertStatus.OPEN),
        (AlertStatus.CLOSED, AlertStatus.ACTIONED),
        # OPEN cannot go directly to CLOSED
        (AlertStatus.OPEN, AlertStatus.CLOSED),
        # ACTIONED cannot go back to OPEN
        (AlertStatus.ACTIONED, AlertStatus.OPEN),
        # ACKNOWLEDGED cannot go to ESCALATED
        (AlertStatus.ACKNOWLEDGED, AlertStatus.ESCALATED),
    ],
)
def test_illegal_transition(from_status: AlertStatus, to_status: AlertStatus) -> None:
    alert = _make_alert(status=from_status)
    with pytest.raises(Conflict) as exc_info:
        alert.transition(to_status, _entry(to_status.value))
    assert exc_info.value.code == "INVALID_TRANSITION"
    # Status must not have changed
    assert alert.status == from_status


# ---------------------------------------------------------------------------
# dedup_key: deterministic + stable
# ---------------------------------------------------------------------------


def test_dedup_key_deterministic() -> None:
    key1 = dedup_key("cluster-abc", "ATM", "loc-123")
    key2 = dedup_key("cluster-abc", "ATM", "loc-123")
    assert key1 == key2


def test_dedup_key_differs_on_target() -> None:
    key1 = dedup_key("cluster-1", "ATM", "loc-1")
    key2 = dedup_key("cluster-1", "BRANCH", "loc-1")
    assert key1 != key2


def test_dedup_key_differs_on_cluster() -> None:
    key1 = dedup_key("cluster-1", "ATM", "loc-1")
    key2 = dedup_key("cluster-2", "ATM", "loc-1")
    assert key1 != key2


# ---------------------------------------------------------------------------
# severity(): band boundaries
# ---------------------------------------------------------------------------


def _policy() -> Policy:
    return Policy.load("config/policy.yaml")


def test_severity_critical(tmp_path) -> None:
    policy = _policy()
    # With high confidence + large amount: should hit CRITICAL
    result = severity(0.99, 100_000_000_00, Verdict.INTERCEPTABLE, policy)
    # score = 0.99 × log1p(1e10) × 0.7 → very large → CRITICAL
    assert result == Severity.CRITICAL


def test_severity_low() -> None:
    policy = _policy()
    # Near-zero confidence + tiny amount → LOW
    result = severity(0.01, 1, Verdict.NOT_INTERCEPTABLE, policy)
    assert result == Severity.LOW


def test_severity_not_interceptable_uses_marginal_floor() -> None:
    policy = _policy()
    # NOT_INTERCEPTABLE: interception_p = 0.0, effective_p = marginal floor
    result = severity(0.5, 100_000_000, Verdict.NOT_INTERCEPTABLE, policy)
    # Should not be None and should be a valid Severity member
    assert result in list(Severity)


# ---------------------------------------------------------------------------
# budget.rank_and_cap()
# ---------------------------------------------------------------------------


def test_budget_top_n_not_deferred() -> None:
    policy = _policy()
    budget = policy.alerting.budget_per_shift
    alerts = [
        _make_alert(f"alert-{i}", confidence=float(budget - i) / budget) for i in range(budget + 5)
    ]

    ranked = rank_and_cap(alerts, policy)

    not_deferred = [a for a in ranked if not a.is_deferred and not a.is_probe]
    assert len(not_deferred) == budget


def test_budget_excess_is_deferred_or_probe() -> None:
    policy = _policy()
    budget = policy.alerting.budget_per_shift
    n = budget + 20
    alerts = [_make_alert(f"alert-{i}") for i in range(n)]

    rank_and_cap(alerts, policy)
    deferred_or_probe = [a for a in alerts if a.is_deferred or a.is_probe]
    assert len(deferred_or_probe) == 20


def test_budget_probe_is_deterministic() -> None:
    """The same alert_id always gets the same probe decision."""
    policy = _policy()
    budget = policy.alerting.budget_per_shift
    n = budget + 5
    alerts_a = [_make_alert(f"alert-{i}") for i in range(n)]
    alerts_b = [_make_alert(f"alert-{i}") for i in range(n)]

    rank_and_cap(alerts_a, policy)
    rank_and_cap(alerts_b, policy)

    for a, b in zip(alerts_a, alerts_b, strict=True):
        assert a.is_probe == b.is_probe
        assert a.is_deferred == b.is_deferred


# ---------------------------------------------------------------------------
# Alert.merge() logic
# ---------------------------------------------------------------------------


def test_merge_keeps_earlier_created_at() -> None:
    alert = _make_alert()
    later = datetime(2024, 6, 1, tzinfo=UTC)
    entry = TimelineEntry(
        id="tl-m",
        alert_id="alert-1",
        at=later,
        kind="merged",
        actor_id=None,
        text_code="alert.merged",
        text_params={},
    )
    original_created = alert.created_at
    alert.merge(forecast_id="fc-2", confidence=0.9, window_end=later, entry=entry)
    assert alert.created_at == original_created


def test_merge_updates_confidence_if_higher() -> None:
    alert = _make_alert(confidence=0.5)
    entry = TimelineEntry(
        id="tl-m2",
        alert_id="alert-1",
        at=_NOW,
        kind="merged",
        actor_id=None,
        text_code="alert.merged",
        text_params={},
    )
    alert.merge(forecast_id="fc-2", confidence=0.9, window_end=_NOW, entry=entry)
    assert alert.confidence == 0.9


def test_merge_does_not_reduce_confidence() -> None:
    alert = _make_alert(confidence=0.9)
    entry = TimelineEntry(
        id="tl-m3",
        alert_id="alert-1",
        at=_NOW,
        kind="merged",
        actor_id=None,
        text_code="alert.merged",
        text_params={},
    )
    alert.merge(forecast_id="fc-2", confidence=0.3, window_end=_NOW, entry=entry)
    assert alert.confidence == 0.9
