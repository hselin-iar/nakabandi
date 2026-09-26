"""repositories.py — SQLAlchemy implementations of interception ports (DOC 3 M6).

Tables owned by the interception module (DOC 3 LC-10):
  units              (id, kind, lat, lon, district_id, active)
  intercept_assessments (id, forecast_id, target_kind, target_id, channel,
                          window_min, best_unit_id, best_unit_kind, best_unit_eta_min,
                          best_unit_lat, best_unit_lon,
                          interception_probability, verdict, ladder_level,
                          reason_code, reason_params_json,
                          disputed_paise, proposed_paise, expires_at, review_at,
                          assessed_at)
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from nakabandi_contracts.enums import LadderLevel, Verdict
from sqlalchemy.orm import Session

from nakabandi.interception.application.ports import AssessmentRepo, UnitRepo
from nakabandi.interception.domain.lien import LienProposal
from nakabandi.interception.domain.types import (
    BestUnit,
    InterceptAssessment,
    ProportionalityView,
    TargetRef,
)
from nakabandi.interception.domain.units import Unit
from nakabandi.shared import Id, SimTime

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

metadata = sa.MetaData()

units_table = sa.Table(
    "units",
    metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("kind", sa.String, nullable=False),
    sa.Column("lat", sa.Float, nullable=False),
    sa.Column("lon", sa.Float, nullable=False),
    sa.Column("district_id", sa.String, nullable=True),
    sa.Column("active", sa.Boolean, nullable=False, default=True),
)

intercept_assessments = sa.Table(
    "intercept_assessments",
    metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("forecast_id", sa.String, nullable=False, index=True),
    sa.Column("target_kind", sa.String, nullable=False),
    sa.Column("target_id", sa.String, nullable=False),
    sa.Column("channel", sa.String, nullable=False),
    sa.Column("window_min", sa.Float, nullable=False),
    sa.Column("best_unit_id", sa.String, nullable=True),
    sa.Column("best_unit_kind", sa.String, nullable=True),
    sa.Column("best_unit_eta_min", sa.Float, nullable=True),
    sa.Column("best_unit_lat", sa.Float, nullable=True),
    sa.Column("best_unit_lon", sa.Float, nullable=True),
    sa.Column("interception_probability", sa.Float, nullable=False),
    sa.Column("verdict", sa.String, nullable=False),
    sa.Column("ladder_level", sa.String, nullable=False),
    sa.Column("reason_code", sa.String, nullable=False),
    sa.Column("reason_params_json", sa.Text, nullable=False, default="{}"),
    sa.Column("disputed_paise", sa.BigInteger, nullable=True),
    sa.Column("proposed_paise", sa.BigInteger, nullable=True),
    sa.Column("lien_expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("lien_review_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
)

# ---------------------------------------------------------------------------
# Repository implementations
# ---------------------------------------------------------------------------


class SqlUnitRepo(UnitRepo):
    def __init__(self, session: Session) -> None:
        self._s = session

    def all_units(self) -> list[Unit]:
        rows = self._s.execute(sa.select(units_table).where(units_table.c.active.is_(True))).all()
        return [
            Unit(id=r.id, kind=r.kind, lat=r.lat, lon=r.lon)
            for r in rows
            if r.lat is not None and r.lon is not None
        ]


class SqlAssessmentRepo(AssessmentRepo):
    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, assessment: InterceptAssessment, as_of: SimTime) -> None:
        lien = assessment.lien_proposal
        self._s.execute(
            sa.insert(intercept_assessments)
            .values(
                id=assessment.id,
                forecast_id=assessment.forecast_id,
                target_kind=assessment.target.kind,
                target_id=assessment.target.id,
                channel=assessment.channel,
                window_min=assessment.window_min,
                best_unit_id=assessment.best_unit.unit_id if assessment.best_unit else None,
                best_unit_kind=assessment.best_unit.unit_kind if assessment.best_unit else None,
                best_unit_eta_min=assessment.best_unit.eta_min if assessment.best_unit else None,
                best_unit_lat=assessment.best_unit.lat if assessment.best_unit else None,
                best_unit_lon=assessment.best_unit.lon if assessment.best_unit else None,
                interception_probability=assessment.interception_probability,
                verdict=assessment.verdict.value,
                ladder_level=assessment.ladder_level.value,
                reason_code=assessment.reason_code,
                reason_params_json=json.dumps(assessment.reason_params),
                disputed_paise=lien.disputed_paise if lien else None,
                proposed_paise=lien.proposed_paise if lien else None,
                lien_expires_at=lien.expires_at if lien else None,
                lien_review_at=lien.review_at if lien else None,
                assessed_at=as_of,
            )
            .prefix_with("OR IGNORE")
        )

    def get_by_forecast(self, forecast_id: Id) -> list[InterceptAssessment]:
        rows = self._s.execute(
            sa.select(intercept_assessments).where(
                intercept_assessments.c.forecast_id == forecast_id
            )
        ).all()
        return [_row_to_assessment(r) for r in rows]


def _row_to_assessment(r: sa.Row) -> InterceptAssessment:  # type: ignore[type-arg]
    best_unit: BestUnit | None = None
    if r.best_unit_id:
        best_unit = BestUnit(
            unit_id=r.best_unit_id,
            unit_kind=r.best_unit_kind or "",
            eta_min=float(r.best_unit_eta_min or 0),
            lat=float(r.best_unit_lat or 0),
            lon=float(r.best_unit_lon or 0),
        )
    lien: LienProposal | None = None
    prop_view: ProportionalityView | None = None
    if r.disputed_paise and r.proposed_paise and r.lien_expires_at and r.lien_review_at:
        # Re-construct without __post_init__ (data already validated on save)
        lien = LienProposal.__new__(LienProposal)
        object.__setattr__(lien, "complaint_id", "")  # not stored; set by use case context
        object.__setattr__(lien, "account_id", "")
        object.__setattr__(lien, "disputed_paise", r.disputed_paise)
        object.__setattr__(lien, "proposed_paise", r.proposed_paise)
        object.__setattr__(lien, "expires_at", r.lien_expires_at)
        object.__setattr__(lien, "review_at", r.lien_review_at)

    return InterceptAssessment(
        id=r.id,
        forecast_id=r.forecast_id,
        target=TargetRef(kind=r.target_kind, id=r.target_id),
        channel=r.channel,
        window_min=float(r.window_min),
        best_unit=best_unit,
        interception_probability=float(r.interception_probability),
        verdict=Verdict(r.verdict),
        ladder_level=LadderLevel(r.ladder_level),
        reason_code=r.reason_code,
        reason_params=json.loads(r.reason_params_json),
        proportionality=prop_view,
        lien_proposal=lien,
    )
