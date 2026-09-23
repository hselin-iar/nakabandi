"""Public facade of the interception module: what other modules may import (DOC 3 M6).

Exports:
  Interceptor       — assess(forecast_id, targets, ...) -> list[InterceptAssessment]
                      validate_lien(...)               -> LienProposal
  InterceptAssessment, ProportionalityView, LienProposal  — value objects
"""

from __future__ import annotations

from nakabandi.interception.application.ports import AssessmentRepo, UnitRepo
from nakabandi.interception.application.use_cases import AssessInterception, ValidateLien
from nakabandi.interception.domain.lien import LienInvalid, LienProposal
from nakabandi.interception.domain.probability import TimingForecast
from nakabandi.interception.domain.travel import HaversineEstimator
from nakabandi.interception.domain.types import (
    InterceptAssessment,
    ProportionalityView,
    TargetRef,
)
from nakabandi.shared import Id, Policy, SimTime

__all__ = [
    "Interceptor",
    "InterceptAssessment",
    "ProportionalityView",
    "LienProposal",
    "LienInvalid",
    "TimingForecast",
    "TargetRef",
]


class Interceptor:
    """Façade: the ONLY interception object other modules may import.

    Instantiate once at startup with repo and policy dependencies.
    """

    def __init__(
        self,
        unit_repo: UnitRepo,
        assessment_repo: AssessmentRepo,
        policy: Policy,
    ) -> None:
        self._estimator = HaversineEstimator(policy)
        self._assess_uc = AssessInterception(
            unit_repo=unit_repo,
            assessment_repo=assessment_repo,
            estimator=self._estimator,
            policy=policy,
        )
        self._validate_uc = ValidateLien(policy)

    def assess(
        self,
        forecast_id: Id,
        targets: list[tuple[TargetRef, str, float, float, float, TimingForecast]],
        complaint_id: Id,
        traced_accounts: list[Id],
        disputed_paise_by_account: dict[Id, int],
        active_lien_totals: dict[Id, int],
        as_of: SimTime,
    ) -> list[InterceptAssessment]:
        """Assess interception for all targets; persist; return assessments.

        Called by pipeline.ProcessComplaint only.
        """
        return self._assess_uc.run(
            forecast_id=forecast_id,
            targets=targets,
            complaint_id=complaint_id,
            traced_accounts=traced_accounts,
            disputed_paise_by_account=disputed_paise_by_account,
            active_lien_totals=active_lien_totals,
            as_of=as_of,
        )

    def validate_lien(
        self,
        complaint_id: Id,
        account_id: Id,
        traced_accounts: list[Id],
        disputed_paise: int,
        proposed_paise: int,
        active_lien_proposed_total: int,
        now: SimTime,
    ) -> LienProposal:
        """Re-validate a proposed lien before a hold-request action.

        Raises LienInvalid on any violation.
        Called by alerting.RecordAction only.
        """
        return self._validate_uc.run(
            complaint_id=complaint_id,
            account_id=account_id,
            traced_accounts=traced_accounts,
            disputed_paise=disputed_paise,
            proposed_paise=proposed_paise,
            active_lien_proposed_total=active_lien_proposed_total,
            now=now,
        )
