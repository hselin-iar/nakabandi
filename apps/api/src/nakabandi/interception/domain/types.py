"""types.py — Interception domain value objects (DOC 3 M6, LC-4).

These are pure domain types; no I/O, no database imports.
InterceptAssessment and ProportionalityView are the LC-4 shapes read by
alerting and the web app.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from nakabandi_contracts.enums import LadderLevel, Verdict

from nakabandi.interception.domain.lien import LienProposal
from nakabandi.shared import Id, SimTime


@dataclass(frozen=True)
class TargetRef:
    """A reference to the forecast target being assessed."""

    kind: str  # "location" | "cell" | "district"
    id: Id


@dataclass(frozen=True)
class BestUnit:
    """The nearest unit and its ETA for a given target."""

    unit_id: Id
    unit_kind: str
    eta_min: float
    lat: float
    lon: float


@dataclass(frozen=True)
class ProportionalityView:
    """Proportionality information shown on the alert detail panel (LC-4)."""

    disputed_paise: int
    proposed_paise: int
    ratio: float
    expires_at: SimTime
    review_at: SimTime
    magistrate_report_reminder: bool
    complaint_ref: Id


@dataclass(frozen=True)
class InterceptAssessment:
    """Full assessment for one target location (LC-4 shape, DOC 3 M6).

    id:                       Unique assessment id (ULID).
    forecast_id:              The forecast this assessment is derived from.
    target:                   The target location, cell, or district.
    channel:                  The predicted cash-out channel.
    window_min:               How long the interception window lasts (minutes).
    best_unit:                Nearest unit and ETA (None if no units in registry).
    interception_probability: P(cash-out not yet happened when unit arrives).
    verdict:                  INTERCEPTABLE | MARGINAL | NOT_INTERCEPTABLE.
    ladder_level:             NONE | L1 | L2 | L3.
    reason_code:              Machine-readable explanation code.
    reason_params:            Params for the reason message (localised by the UI).
    proportionality:          Lien proportionality view (only for L1 level).
    lien_proposal:            The proposed lien (only for L1 level; None otherwise).
    """

    id: Id
    forecast_id: Id
    target: TargetRef
    channel: str
    window_min: float
    best_unit: BestUnit | None
    interception_probability: float
    verdict: Verdict
    ladder_level: LadderLevel
    reason_code: str
    reason_params: dict[str, str] = field(default_factory=dict)
    proportionality: ProportionalityView | None = None
    lien_proposal: LienProposal | None = None
