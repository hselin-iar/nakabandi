"""SimConfig — typed model of config/sim.default.yaml (DOC 3 M1).

Pure data class; no I/O. Loaded by the runner and CLI, never by domain code directly.
All keys are frozen (equivalent to LC-7 for the simulator). Unknown or missing keys abort
load (same policy as shared/policy.py).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class LoadConfig(BaseModel):
    complaints_per_day: float = Field(gt=0)


class AmountsConfig(BaseModel):
    mean_paise: int = Field(gt=0)
    shape_sigma: float = Field(gt=0, default=1.2)


class NetworkConfig(BaseModel):
    layers_min: int = Field(ge=2, default=2)
    layers_max: int = Field(le=12, default=12)
    layers_median: int = Field(ge=2, le=12, default=4)
    accounts_per_cluster: int = Field(gt=0)
    bridge_rate: float = Field(ge=0.0, le=1.0)
    hop_visibility: float = Field(ge=0.0, le=1.0)


class CapsConfig(BaseModel):
    card_atm_daily_inr: int = Field(gt=0)
    cardless_atm_txn_inr: int = Field(gt=0)
    aeps_txn_inr: int = Field(gt=0)
    aeps_daily_inr: int = Field(gt=0)


class TimingComponent(BaseModel):
    weight: float = Field(gt=0, le=1.0)
    component: Literal["fast", "slow"]
    lognormal_median_min: float = Field(gt=0)
    lognormal_sigma: float = Field(gt=0)


class TimingConfig(BaseModel):
    mixture: list[TimingComponent] = Field(min_length=1)

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> TimingConfig:
        total = sum(c.weight for c in self.mixture)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"timing.mixture weights must sum to 1.0, got {total:.6f}")
        return self


class ChannelsConfig(BaseModel):
    mix: dict[Literal["ATM", "BRANCH", "AGENT"], float]

    @model_validator(mode="after")
    def mix_sums_to_one(self) -> ChannelsConfig:
        total = sum(self.mix.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"channels.mix weights must sum to 1.0, got {total:.6f}")
        return self


class FootprintConfig(BaseModel):
    locality: Literal["district", "multi_district", "state", "multi_state"] = "district"
    size_per_cluster: int = Field(gt=0)


class MuleConfig(BaseModel):
    lifetime_days: float = Field(gt=0)


class GeoConfig(BaseModel):
    state_weights: dict[str, float]

    @model_validator(mode="after")
    def weights_positive(self) -> GeoConfig:
        for k, v in self.state_weights.items():
            if v <= 0:
                raise ValueError(f"geo.state_weights[{k!r}] must be > 0, got {v}")
        return self


class KitConfig(BaseModel):
    cards_per_account: int = Field(ge=1)


class NoiseConfig(BaseModel):
    innocent_layer1_rate: float = Field(ge=0.0, le=1.0)


class LagConfig(BaseModel):
    min: float = Field(ge=0.0)
    max: float = Field(gt=0.0)
    median: float = Field(gt=0.0)

    @model_validator(mode="after")
    def order_check(self) -> LagConfig:
        if not (self.min <= self.median <= self.max):
            raise ValueError("lag requires min <= median <= max")
        return self


class WorldConfig(BaseModel):
    days: int = Field(ge=1)
    n_clusters: int = Field(ge=1)


# ---------------------------------------------------------------------------
# Top-level SimConfig
# ---------------------------------------------------------------------------


class SimConfig(BaseModel):
    """Top-level simulator configuration. Loaded from config/sim.default.yaml."""

    seed: int = 42
    world: WorldConfig
    load: LoadConfig
    amounts: AmountsConfig
    network: NetworkConfig
    caps: CapsConfig
    timing: TimingConfig
    channels: ChannelsConfig
    footprint: FootprintConfig
    mule: MuleConfig
    geo: GeoConfig
    kit: KitConfig
    noise: NoiseConfig
    lag: LagConfig

    model_config = {"extra": "forbid"}  # unknown keys abort load

    @classmethod
    def from_yaml(cls, path: Path | str = "config/sim.default.yaml") -> SimConfig:
        """Load and validate from a YAML file. Raises on error with a clear message."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"SimConfig: file not found: {p}")
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        if raw is None:
            raise ValueError(f"SimConfig: empty config file: {p}")
        return cls.model_validate(raw)
