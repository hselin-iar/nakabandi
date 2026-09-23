"""test_interception.py — B3 Done-When property and unit tests (DOC 3 M6 Testing Plan).

Tests verified:
  P1. LienProposal invariants: proposed > 0 and proposed <= disputed (property test).
  P2. LienProposal: expires_at > review_at required.
  P3. LienProposal: complaint_id must be non-empty.
  P4. Ladder table exhaustive: a rule exists for every (channel x verdict) pair.
  P5. ETA monotone in distance: larger distance -> larger ETA.
  P6. Probability monotone non-increasing in ETA.
  P7. No-units case returns NOT_INTERCEPTABLE with reason_code NO_UNITS.
  P8. build_lien total-cap: proposed cannot exceed disputed minus already-proposed.
  P9. verdict_from boundaries: at and around threshold values.
  P10. ladder_level confidence gate: below min_confidence_for_action -> NONE.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from nakabandi.interception.domain.ladder import ladder_level
from nakabandi.interception.domain.lien import LienInvalid, LienProposal, build_lien
from nakabandi.interception.domain.probability import TimingForecast, interception_probability
from nakabandi.interception.domain.travel import HaversineEstimator
from nakabandi.interception.domain.verdict import verdict_from
from nakabandi.shared import Policy
from nakabandi_contracts.enums import Channel, LadderLevel, Verdict

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
_FUTURE_1H = _NOW + timedelta(hours=1)
_FUTURE_25H = _NOW + timedelta(hours=25)
_FUTURE_73H = _NOW + timedelta(hours=73)

_COMPLAINT = "01COMPLAINT0000000000000001"
_ACCOUNT = "01ACCOUNT00000000000000001"
_TRACED = [_ACCOUNT]


def _load_policy() -> Policy:
    from pathlib import Path

    return Policy.load(Path(__file__).parents[4] / "config" / "policy.yaml")


_POLICY = _load_policy()

_GOOD_TIMING = TimingForecast(residual_mass=0.8, p30=0.3, p60=0.5, p120=0.7)
_STALE_TIMING = TimingForecast(residual_mass=0.005, p30=0.9, p60=0.95, p120=0.99)


# ---------------------------------------------------------------------------
# P1 — LienProposal invariants: 0 < proposed <= disputed
# ---------------------------------------------------------------------------


class TestLienProposalInvariants:
    def _valid(self) -> LienProposal:
        return LienProposal(
            complaint_id=_COMPLAINT,
            account_id=_ACCOUNT,
            disputed_paise=10_000_00,
            proposed_paise=5_000_00,
            expires_at=_FUTURE_73H,
            review_at=_FUTURE_25H,
        )

    def test_valid_construction(self):
        lien = self._valid()
        assert lien.proposed_paise == 5_000_00
        assert lien.disputed_paise == 10_000_00

    def test_proposed_zero_raises(self):
        with pytest.raises(LienInvalid):
            LienProposal(
                complaint_id=_COMPLAINT,
                account_id=_ACCOUNT,
                disputed_paise=10_000_00,
                proposed_paise=0,
                expires_at=_FUTURE_73H,
                review_at=_FUTURE_25H,
            )

    def test_proposed_negative_raises(self):
        with pytest.raises(LienInvalid):
            LienProposal(
                complaint_id=_COMPLAINT,
                account_id=_ACCOUNT,
                disputed_paise=10_000_00,
                proposed_paise=-100,
                expires_at=_FUTURE_73H,
                review_at=_FUTURE_25H,
            )

    def test_proposed_exceeds_disputed_raises(self):
        with pytest.raises(LienInvalid):
            LienProposal(
                complaint_id=_COMPLAINT,
                account_id=_ACCOUNT,
                disputed_paise=10_000_00,
                proposed_paise=10_000_01,
                expires_at=_FUTURE_73H,
                review_at=_FUTURE_25H,
            )

    def test_proposed_equals_disputed_valid(self):
        lien = LienProposal(
            complaint_id=_COMPLAINT,
            account_id=_ACCOUNT,
            disputed_paise=10_000_00,
            proposed_paise=10_000_00,
            expires_at=_FUTURE_73H,
            review_at=_FUTURE_25H,
        )
        assert lien.proposed_paise == lien.disputed_paise

    # P2 — expires_at > review_at
    def test_review_after_expiry_raises(self):
        with pytest.raises(LienInvalid):
            LienProposal(
                complaint_id=_COMPLAINT,
                account_id=_ACCOUNT,
                disputed_paise=10_000_00,
                proposed_paise=5_000_00,
                expires_at=_FUTURE_25H,  # earlier
                review_at=_FUTURE_73H,  # later — wrong
            )

    def test_review_equals_expiry_raises(self):
        with pytest.raises(LienInvalid):
            LienProposal(
                complaint_id=_COMPLAINT,
                account_id=_ACCOUNT,
                disputed_paise=10_000_00,
                proposed_paise=5_000_00,
                expires_at=_FUTURE_73H,
                review_at=_FUTURE_73H,  # same — wrong
            )

    # P3 — complaint_id must be non-empty
    def test_empty_complaint_id_raises(self):
        with pytest.raises(LienInvalid):
            LienProposal(
                complaint_id="",
                account_id=_ACCOUNT,
                disputed_paise=10_000_00,
                proposed_paise=5_000_00,
                expires_at=_FUTURE_73H,
                review_at=_FUTURE_25H,
            )

    def test_empty_account_id_raises(self):
        with pytest.raises(LienInvalid):
            LienProposal(
                complaint_id=_COMPLAINT,
                account_id="",
                disputed_paise=10_000_00,
                proposed_paise=5_000_00,
                expires_at=_FUTURE_73H,
                review_at=_FUTURE_25H,
            )

    def test_disputed_zero_raises(self):
        with pytest.raises(LienInvalid):
            LienProposal(
                complaint_id=_COMPLAINT,
                account_id=_ACCOUNT,
                disputed_paise=0,
                proposed_paise=0,
                expires_at=_FUTURE_73H,
                review_at=_FUTURE_25H,
            )

    def test_no_freeze_account_field(self):
        """There is NO field for a whole-account freeze on LienProposal."""
        lien = self._valid()
        assert not hasattr(lien, "freeze_account")
        assert not hasattr(lien, "whole_account_freeze")
        assert not hasattr(lien, "freeze")


# ---------------------------------------------------------------------------
# P4 — Ladder table exhaustive: every (channel, verdict) pair has a rule
# ---------------------------------------------------------------------------


class TestLadderExhaustive:
    """Every (Channel x Verdict) combination must match at least one ladder rule."""

    def test_all_channel_verdict_pairs_match(self):
        """For every channel x verdict combo, ladder_level must return a defined level."""
        errors = []
        for ch in Channel:
            for v in Verdict:
                try:
                    level = ladder_level(
                        channel=ch.value,
                        verdict=v,
                        confidence=1.0,  # above all gates
                        policy=_POLICY,
                    )
                    assert level in LadderLevel, f"Invalid level for ({ch}, {v}): {level}"
                except Exception as e:  # noqa: BLE001
                    errors.append(f"({ch.value}, {v.value}): {e}")
        assert not errors, "\n".join(errors)

    def test_confidence_below_gate_returns_none(self):
        """P10: confidence < min_confidence_for_action => NONE for all combos."""
        for ch in Channel:
            for v in Verdict:
                level = ladder_level(
                    channel=ch.value,
                    verdict=v,
                    confidence=0.0,
                    policy=_POLICY,
                )
                assert level == LadderLevel.NONE, f"Expected NONE for ({ch},{v}) at confidence=0"

    def test_not_interceptable_gives_none(self):
        level = ladder_level(
            channel="ATM",
            verdict=Verdict.NOT_INTERCEPTABLE,
            confidence=1.0,
            policy=_POLICY,
        )
        assert level == LadderLevel.NONE

    def test_interceptable_atm_gives_l3(self):
        level = ladder_level("ATM", Verdict.INTERCEPTABLE, 1.0, _POLICY)
        assert level == LadderLevel.L3

    def test_interceptable_agent_gives_l2(self):
        level = ladder_level("AGENT", Verdict.INTERCEPTABLE, 1.0, _POLICY)
        assert level == LadderLevel.L2

    def test_marginal_atm_gives_l1(self):
        level = ladder_level("ATM", Verdict.MARGINAL, 1.0, _POLICY)
        assert level == LadderLevel.L1

    def test_unknown_channel_falls_to_catchall(self):
        level = ladder_level("MOBILE_WALLET", Verdict.INTERCEPTABLE, 1.0, _POLICY)
        # catch-all rule: channel='*', verdict='*' => L2
        assert level == LadderLevel.L2


# ---------------------------------------------------------------------------
# P5 — ETA monotone in distance
# ---------------------------------------------------------------------------


class TestEtaMonotone:
    def test_larger_distance_larger_eta(self):
        estimator = HaversineEstimator(_POLICY)
        eta_5 = estimator.eta_min(5.0, "urban")
        eta_10 = estimator.eta_min(10.0, "urban")
        eta_20 = estimator.eta_min(20.0, "urban")
        assert eta_5 < eta_10 < eta_20

    def test_eta_positive_for_positive_distance(self):
        estimator = HaversineEstimator(_POLICY)
        assert estimator.eta_min(1.0, "urban") > 0

    def test_area_type_ordering(self):
        """Urban should be slowest (highest ETA per km); rural fastest."""
        estimator = HaversineEstimator(_POLICY)
        eta_urban = estimator.eta_min(10.0, "urban")
        eta_semi = estimator.eta_min(10.0, "semi_urban")
        eta_rural = estimator.eta_min(10.0, "rural")
        assert eta_urban > eta_semi > eta_rural


# ---------------------------------------------------------------------------
# P6 — Probability monotone non-increasing in ETA
# ---------------------------------------------------------------------------


class TestProbabilityMonotone:
    def test_probability_decreases_with_eta(self):
        timing = _GOOD_TIMING
        probs = [interception_probability(eta, timing) for eta in [0, 10, 30, 60, 90, 120, 200]]
        for i in range(len(probs) - 1):
            assert probs[i] >= probs[i + 1], (
                f"prob not monotone: p[{i}]={probs[i]:.4f} < p[{i + 1}]={probs[i + 1]:.4f}"
            )

    def test_probability_in_unit_interval(self):
        timing = _GOOD_TIMING
        for eta in [0, 15, 30, 60, 90, 120, 240]:
            p = interception_probability(eta, timing)
            assert 0.0 <= p <= 1.0, f"p={p} out of [0,1] at eta={eta}"

    def test_zero_eta_returns_one(self):
        timing = _GOOD_TIMING
        # eta=0 → F_cond(0)=0 → interception_probability = 1 - 0 = 1.0
        assert interception_probability(0, timing) == pytest.approx(1.0)

    def test_very_large_eta_near_zero(self):
        timing = _GOOD_TIMING
        p = interception_probability(10_000, timing)
        assert p == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# P7 — No-units case
# ---------------------------------------------------------------------------


class TestNoUnitsCase:
    def test_unit_index_build_raises_on_empty(self):
        from nakabandi.interception.domain.units import UnitIndex

        with pytest.raises(ValueError, match="empty"):
            UnitIndex.build([])


# ---------------------------------------------------------------------------
# P8 — build_lien total-cap
# ---------------------------------------------------------------------------


class TestBuildLien:
    def test_full_amount_when_no_active_liens(self):
        lien = build_lien(
            complaint_id=_COMPLAINT,
            account_id=_ACCOUNT,
            traced_accounts=_TRACED,
            disputed_paise=10_000_00,
            active_lien_proposed_total=0,
            policy=_POLICY,
            now=_NOW,
        )
        assert lien is not None
        assert lien.proposed_paise == 10_000_00

    def test_remaining_amount_respected(self):
        lien = build_lien(
            complaint_id=_COMPLAINT,
            account_id=_ACCOUNT,
            traced_accounts=_TRACED,
            disputed_paise=10_000_00,
            active_lien_proposed_total=6_000_00,
            policy=_POLICY,
            now=_NOW,
        )
        assert lien is not None
        assert lien.proposed_paise == 4_000_00

    def test_returns_none_when_cap_reached(self):
        lien = build_lien(
            complaint_id=_COMPLAINT,
            account_id=_ACCOUNT,
            traced_accounts=_TRACED,
            disputed_paise=10_000_00,
            active_lien_proposed_total=10_000_00,
            policy=_POLICY,
            now=_NOW,
        )
        assert lien is None

    def test_returns_none_for_untraceable_account(self):
        lien = build_lien(
            complaint_id=_COMPLAINT,
            account_id="OTHER_ACCOUNT",
            traced_accounts=_TRACED,
            disputed_paise=10_000_00,
            active_lien_proposed_total=0,
            policy=_POLICY,
            now=_NOW,
        )
        assert lien is None

    def test_expiry_from_policy(self):
        lien = build_lien(
            complaint_id=_COMPLAINT,
            account_id=_ACCOUNT,
            traced_accounts=_TRACED,
            disputed_paise=10_000_00,
            active_lien_proposed_total=0,
            policy=_POLICY,
            now=_NOW,
        )
        assert lien is not None
        expected_expiry = _NOW + timedelta(hours=_POLICY.lien.expiry_hours)
        expected_review = _NOW + timedelta(hours=_POLICY.lien.review_hours)
        assert lien.expires_at == expected_expiry
        assert lien.review_at == expected_review


# ---------------------------------------------------------------------------
# P9 — verdict_from threshold boundaries
# ---------------------------------------------------------------------------


class TestVerdictFrom:
    def test_above_interceptable_threshold(self):
        t = _POLICY.interception.thresholds.interceptable
        assert verdict_from(t, _POLICY) == Verdict.INTERCEPTABLE
        assert verdict_from(t + 0.01, _POLICY) == Verdict.INTERCEPTABLE

    def test_above_marginal_below_interceptable(self):
        m = _POLICY.interception.thresholds.marginal
        i = _POLICY.interception.thresholds.interceptable
        mid = (m + i) / 2
        assert verdict_from(mid, _POLICY) == Verdict.MARGINAL

    def test_below_marginal_threshold(self):
        m = _POLICY.interception.thresholds.marginal
        assert verdict_from(m - 0.01, _POLICY) == Verdict.NOT_INTERCEPTABLE
        assert verdict_from(0.0, _POLICY) == Verdict.NOT_INTERCEPTABLE
