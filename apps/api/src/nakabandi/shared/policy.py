"""Policy: a typed model of config/policy.yaml (DOC 3 Shared Kernel, LC-7).

LC-7 freezes the key names; the values in config/policy.yaml are tunable (Track B calibrates
and sweeps many of them later). Every model here forbids unknown fields and requires every
field (no Python-level defaults), so a config file missing a key, or carrying an extra one,
aborts boot with a clear key path rather than booting on a partial or drifted policy.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from nakabandi_contracts.enums import Channel, LadderLevel, Permission, Role, Verdict
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator


class PolicyLoadError(RuntimeError):
    """Raised by Policy.load() when config/policy.yaml is missing, malformed, or fails
    validation. Message lists the offending key path(s) so the operator can fix the file."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ForecastCandidatesPolicy(_Strict):
    max: int
    radius_km: float
    widen_factor: float


class ForecastAbstainMinConfidence(_Strict):
    district: float
    cell: float
    location: float


class ForecastAbstainPolicy(_Strict):
    min_confidence: ForecastAbstainMinConfidence


class ForecastTimingPolicy(_Strict):
    n0: float
    n_min: int


class ForecastPolicy(_Strict):
    horizons_min: list[int]
    candidates: ForecastCandidatesPolicy
    abstain: ForecastAbstainPolicy
    stale_residual_mass: float
    novelty_threshold: float
    novel_confidence_cap: float
    timing: ForecastTimingPolicy


class InterceptionSpeedKmh(_Strict):
    urban: float
    semi_urban: float
    rural: float


class InterceptionThresholds(_Strict):
    interceptable: float
    marginal: float

    @model_validator(mode="after")
    def _ordered(self) -> InterceptionThresholds:
        if not (0 <= self.marginal <= self.interceptable <= 1):
            raise ValueError("require 0 <= marginal <= interceptable <= 1")
        return self


class LadderRule(_Strict):
    """First matching rule wins (interception module, a later step). `*` matches any value."""

    channel: str
    verdict: str
    level: LadderLevel

    @field_validator("channel")
    @classmethod
    def _valid_channel(cls, v: str) -> str:
        if v != "*" and v not in {c.value for c in Channel}:
            raise ValueError(f"channel must be '*' or one of {[c.value for c in Channel]}")
        return v

    @field_validator("verdict")
    @classmethod
    def _valid_verdict(cls, v: str) -> str:
        if v != "*" and v not in {v_.value for v_ in Verdict}:
            raise ValueError(f"verdict must be '*' or one of {[v_.value for v_ in Verdict]}")
        return v


class InterceptionPolicy(_Strict):
    speed_kmh: InterceptionSpeedKmh
    road_factor: float
    thresholds: InterceptionThresholds
    targets: int
    min_confidence_for_action: float
    ladder: list[LadderRule]

    @field_validator("ladder")
    @classmethod
    def _has_catch_all(cls, v: list[LadderRule]) -> list[LadderRule]:
        if not any(r.channel == "*" and r.verdict == "*" for r in v):
            raise ValueError("ladder must end with a catch-all rule (channel='*', verdict='*')")
        return v


class LienPolicy(_Strict):
    expiry_hours: float
    review_hours: float

    @model_validator(mode="after")
    def _review_before_expiry(self) -> LienPolicy:
        if not (0 < self.review_hours < self.expiry_hours):
            raise ValueError("require 0 < review_hours < expiry_hours")
        return self


class AlertingSeverityBands(_Strict):
    critical: float
    high: float
    medium: float


class AlertingReviewQueue(_Strict):
    size: int


class AlertingDelivery(_Strict):
    max_attempts: int
    backoff_s: float


class AlertingSms(_Strict):
    max_segments: int


class AlertingPolicy(_Strict):
    floor_confidence: float
    severity_bands: AlertingSeverityBands
    budget_per_shift: int
    shift_hours: float
    exploration_share: float
    escalate_after_min: float
    expire_grace_min: float
    refresh_min: float
    dedup_window_min: float
    review_queue: AlertingReviewQueue
    delivery: AlertingDelivery
    sms: AlertingSms


class OutcomePolicy(_Strict):
    grace_hours: float


class HeatmapPolicy(_Strict):
    k_threshold: int
    potential_lookback_hours: float
    decay_half_life_hours: float
    amount_bands: list[int]
    confidence_bands: list[float]


class FeedbackPolicy(_Strict):
    label_rate: float


class CaseworkPolicy(_Strict):
    bundle_debounce_min: float
    """DOC 3 S1 "Case rebuild is debounced (once per cluster per sim hour)"."""


class AccessPolicy(_Strict):
    permissions: dict[str, list[str]]

    @field_validator("permissions")
    @classmethod
    def _valid_roles_and_permissions(cls, v: dict[str, list[str]]) -> dict[str, list[str]]:
        valid_roles = {r.value for r in Role}
        valid_perms = {p.value for p in Permission}
        for role, perms in v.items():
            if role not in valid_roles:
                raise ValueError(f"unknown role '{role}'; must be one of {sorted(valid_roles)}")
            for perm in perms:
                if perm not in valid_perms:
                    raise ValueError(f"unknown permission '{perm}' for role '{role}'")
        return v


class Policy(_Strict):
    forecast: ForecastPolicy
    interception: InterceptionPolicy
    lien: LienPolicy
    alerting: AlertingPolicy
    outcome: OutcomePolicy
    heatmap: HeatmapPolicy
    access: AccessPolicy
    feedback: FeedbackPolicy
    casework: CaseworkPolicy

    @classmethod
    def load(cls, path: str | Path) -> Policy:
        """Read and validate config/policy.yaml. Aborts (raises PolicyLoadError) on a missing
        file, invalid YAML, a missing key, an extra key, or a key of the wrong type; the error
        message names the offending key path(s)."""
        p = Path(path)
        if not p.exists():
            raise PolicyLoadError(f"policy file not found: {p}")
        try:
            raw: Any = yaml.safe_load(p.read_text())
        except yaml.YAMLError as exc:
            raise PolicyLoadError(f"{p} is not valid YAML: {exc}") from exc
        if not isinstance(raw, dict):
            raise PolicyLoadError(f"{p} must contain a mapping at the top level")
        try:
            return cls.model_validate(raw)
        except ValidationError as exc:
            paths = ", ".join(".".join(str(p) for p in e["loc"]) for e in exc.errors())
            raise PolicyLoadError(f"{p} failed validation at: {paths}") from exc
