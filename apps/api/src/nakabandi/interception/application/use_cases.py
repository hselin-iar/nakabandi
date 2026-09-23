"""use_cases.py — AssessInterception and ValidateLien (DOC 3 M6).

AssessInterception: orchestrates the domain functions for each target.
ValidateLien: re-validates a LienProposal before a RecordAction hold-request.
"""

from __future__ import annotations

import structlog
from nakabandi_contracts.enums import LadderLevel

from nakabandi.interception.application.ports import AssessmentRepo, UnitRepo
from nakabandi.interception.domain.ladder import ladder_level
from nakabandi.interception.domain.lien import LienInvalid, LienProposal, build_lien
from nakabandi.interception.domain.probability import TimingForecast, interception_probability
from nakabandi.interception.domain.travel import HaversineEstimator
from nakabandi.interception.domain.types import (
    BestUnit,
    InterceptAssessment,
    ProportionalityView,
    TargetRef,
)
from nakabandi.interception.domain.units import UnitEta, UnitIndex
from nakabandi.interception.domain.verdict import verdict_from
from nakabandi.shared import Id, Policy, SimTime, new_id

logger = structlog.get_logger(__name__)

# Reason codes (stable; localised by the UI from messages.py)
_RC_NO_UNITS = "NO_UNITS"
_RC_STALE = "TIMING_STALE"
_RC_NORMAL = "OK"
_RC_UNKNOWN_CHANNEL = "UNKNOWN_CHANNEL"


class AssessInterception:
    """Produce an InterceptAssessment for each qualifying target.

    Called by pipeline.ProcessComplaint after the forecast is generated.
    Handles the no-units case gracefully (returns NOT_INTERCEPTABLE / NO_UNITS).
    """

    def __init__(
        self,
        unit_repo: UnitRepo,
        assessment_repo: AssessmentRepo,
        estimator: HaversineEstimator,
        policy: Policy,
    ) -> None:
        self._unit_repo = unit_repo
        self._assessment_repo = assessment_repo
        self._estimator = estimator
        self._policy = policy
        self._unit_index: UnitIndex | None = None

    def _get_index(self) -> UnitIndex | None:
        """Lazily build the UnitIndex from the repo (cached for this instance)."""
        if self._unit_index is None:
            units = self._unit_repo.all_units()
            if not units:
                return None
            self._unit_index = UnitIndex.build(units)
        return self._unit_index

    def run(
        self,
        forecast_id: Id,
        targets: list[tuple[TargetRef, str, float, float, float, TimingForecast]],
        complaint_id: Id,
        traced_accounts: list[Id],
        disputed_paise_by_account: dict[Id, int],
        active_lien_totals: dict[Id, int],
        as_of: SimTime,
    ) -> list[InterceptAssessment]:
        """Assess all targets.

        Parameters
        ----------
        targets:
            List of (TargetRef, channel, lat, lon, confidence, timing) tuples.
        complaint_id:
            The complaint being processed.
        traced_accounts:
            All accounts traced to this complaint.
        disputed_paise_by_account:
            {account_id: disputed_paise} for lien construction.
        active_lien_totals:
            {account_id: sum_of_proposed_paise} for already-active liens.
        as_of:
            Sim-clock time (LC-2).
        """
        index = self._get_index()
        assessments: list[InterceptAssessment] = []
        targets_to_assess = targets[: self._policy.interception.targets]

        for target, channel, lat, lon, confidence, timing in targets_to_assess:
            assessment = self._assess_one(
                forecast_id=forecast_id,
                target=target,
                channel=channel,
                lat=lat,
                lon=lon,
                confidence=confidence,
                timing=timing,
                unit_index=index,
                complaint_id=complaint_id,
                traced_accounts=traced_accounts,
                disputed_paise_by_account=disputed_paise_by_account,
                active_lien_totals=active_lien_totals,
                as_of=as_of,
            )
            assessments.append(assessment)
            self._assessment_repo.save(assessment, as_of)

        return assessments

    def _assess_one(
        self,
        forecast_id: Id,
        target: TargetRef,
        channel: str,
        lat: float,
        lon: float,
        confidence: float,
        timing: TimingForecast,
        unit_index: UnitIndex | None,
        complaint_id: Id,
        traced_accounts: list[Id],
        disputed_paise_by_account: dict[Id, int],
        active_lien_totals: dict[Id, int],
        as_of: SimTime,
    ) -> InterceptAssessment:
        # No units case
        if unit_index is None:
            return InterceptAssessment(
                id=new_id(),
                forecast_id=forecast_id,
                target=target,
                channel=channel,
                window_min=0.0,
                best_unit=None,
                interception_probability=0.0,
                verdict=verdict_from(0.0, self._policy),
                ladder_level=LadderLevel.NONE,
                reason_code=_RC_NO_UNITS,
            )

        # Stale timing
        if timing.residual_mass < 0.01:
            return InterceptAssessment(
                id=new_id(),
                forecast_id=forecast_id,
                target=target,
                channel=channel,
                window_min=0.0,
                best_unit=None,
                interception_probability=0.0,
                verdict=verdict_from(0.0, self._policy),
                ladder_level=LadderLevel.NONE,
                reason_code=_RC_STALE,
            )

        # Get nearest unit; infer area_type from channel (heuristic)
        unit_etas: list[UnitEta] = unit_index.nearest(lat, lon, k=1)
        best_raw = unit_etas[0]
        area_type = _area_type_for_channel(channel)
        eta = self._estimator.eta_min(best_raw.eta_min, area_type)  # best_raw.eta_min is km

        prob = interception_probability(eta, timing)
        verd = verdict_from(prob, self._policy)
        level = ladder_level(channel, verd, confidence, self._policy)

        best_unit = BestUnit(unit_id=best_raw.unit_id, unit_kind=best_raw.unit_kind, eta_min=eta)

        # Build lien for L1 level only
        lien: LienProposal | None = None
        prop_view: ProportionalityView | None = None
        if level == LadderLevel.L1:
            # Use the first traced account as the default lien target (alerting picks per-action)
            for acc in traced_accounts:
                disputed = disputed_paise_by_account.get(acc, 0)
                already_proposed = active_lien_totals.get(acc, 0)
                lien = build_lien(
                    complaint_id=complaint_id,
                    account_id=acc,
                    traced_accounts=traced_accounts,
                    disputed_paise=disputed,
                    active_lien_proposed_total=already_proposed,
                    policy=self._policy,
                    now=as_of,
                )
                if lien is not None:
                    prop_view = ProportionalityView(
                        disputed_paise=lien.disputed_paise,
                        proposed_paise=lien.proposed_paise,
                        ratio=lien.proposed_paise / lien.disputed_paise,
                        expires_at=lien.expires_at,
                        review_at=lien.review_at,
                        magistrate_report_reminder=True,
                        complaint_ref=complaint_id,
                    )
                    break

        reason_code = (
            _RC_UNKNOWN_CHANNEL if channel not in {"ATM", "BRANCH", "AGENT"} else _RC_NORMAL
        )

        return InterceptAssessment(
            id=new_id(),
            forecast_id=forecast_id,
            target=target,
            channel=channel,
            window_min=eta,
            best_unit=best_unit,
            interception_probability=prob,
            verdict=verd,
            ladder_level=level,
            reason_code=reason_code,
            proportionality=prop_view,
            lien_proposal=lien,
        )


def _area_type_for_channel(channel: str) -> str:
    """Heuristic: ATM/BRANCH tend to be urban; AGENT semi_urban."""
    if channel in ("ATM", "BRANCH"):
        return "urban"
    if channel == "AGENT":
        return "semi_urban"
    return "urban"  # unknown → conservative


class ValidateLien:
    """Re-validate a LienProposal before a RecordAction hold-request.

    Called by alerting.RecordAction; raises LienInvalid on any violation.
    """

    def __init__(self, policy: Policy) -> None:
        self._policy = policy

    def run(
        self,
        complaint_id: Id,
        account_id: Id,
        traced_accounts: list[Id],
        disputed_paise: int,
        proposed_paise: int,
        active_lien_proposed_total: int,
        now: SimTime,
    ) -> LienProposal:
        """Validate and reconstruct a LienProposal.

        Raises LienInvalid if the proposed amount exceeds what is allowed.
        """
        from datetime import timedelta

        remaining = disputed_paise - active_lien_proposed_total
        if proposed_paise > remaining:
            raise LienInvalid(
                "LIEN_EXCEEDS_REMAINING",
                f"proposed ({proposed_paise}) exceeds remaining holdable amount ({remaining})",
            )
        if account_id not in traced_accounts:
            raise LienInvalid("LIEN_ACCOUNT_NOT_TRACED", f"{account_id} not in traced accounts")

        expiry_hours = self._policy.lien.expiry_hours
        review_hours = self._policy.lien.review_hours

        return LienProposal(
            complaint_id=complaint_id,
            account_id=account_id,
            disputed_paise=disputed_paise,
            proposed_paise=proposed_paise,
            expires_at=now + timedelta(hours=expiry_hours),
            review_at=now + timedelta(hours=review_hours),
        )
