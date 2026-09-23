"""config.py — ExperimentConfig and SweepGrid (DOC 3 Evaluation Harness B7).

ExperimentConfig is the unit of work for one experiment run.
config_hash is deterministic: same seed + parameters → same hash → same rows.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SweepGrid:
    """Parameter grid for expand_grid().

    timing_medians_min: list of timing-median values to sweep (minutes)
    channel_mixes:      list of channel-mix labels (e.g. "atm_heavy", "upi_heavy", "mixed")
    localities:         list of locality labels (e.g. "local", "dispersed")
    """

    timing_medians_min: tuple[float, ...] = (15.0, 60.0, 240.0)
    channel_mixes: tuple[str, ...] = ("atm_heavy", "mixed", "upi_heavy")
    localities: tuple[str, ...] = ("local", "dispersed")


@dataclass(frozen=True)
class ExperimentConfig:
    """Fully-specified config for one experiment run.

    seed:          RNG seed for the world-sim (deterministic worlds)
    days_history:  days of simulated history used for training
    days_test:     days replayed for evaluation (held-out)
    n_clusters:    number of mule clusters in the world
    n_per_day:     complaints per simulated day
    timing_median_min: median cash-out delay for this cell
    channel_mix:   one of ("atm_heavy", "mixed", "upi_heavy")
    locality:      one of ("local", "dispersed")
    top_k:         k for hit_rate@k and precision@k
    oracle_url:    base URL of the world-sim oracle API (localhost only)
    model_store_dir: path for trained model artefacts (temp dir per run)
    """

    seed: int = 42
    days_history: int = 5
    days_test: int = 2
    n_clusters: int = 6
    n_per_day: int = 100
    timing_median_min: float = 60.0
    channel_mix: str = "mixed"
    locality: str = "local"
    top_k: int = 5
    oracle_url: str = "http://localhost:8001"
    model_store_dir: str = ""  # empty → tempdir per run

    # Extra free-form sweep metadata (not used in hash by default)
    sweep_key: str = ""

    def config_hash(self) -> str:
        """SHA-256 of the config dict, stable across Python runs."""
        d: dict[str, Any] = {
            k: v for k, v in asdict(self).items() if k not in ("oracle_url", "model_store_dir")
        }
        blob = json.dumps(d, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


@dataclass
class BinStat:
    """One bucket from a reliability curve."""

    bin_lower: float
    bin_upper: float
    fraction_of_positives: float
    mean_predicted_value: float
    n: int


@dataclass
class LeadTimeStats:
    """Summary statistics for lead-time distribution (minutes)."""

    median: float
    p10: float
    p90: float
    n: int


@dataclass
class ShareStats:
    """Precision / recall of interceptable share."""

    precision: float
    recall: float
    n_predicted: int
    n_true: int


@dataclass
class CurvePoint:
    """One point on the cold-start curve."""

    bucket: str  # e.g. "0 prior cashouts", "1-3 prior cashouts", "4+"
    hit_rate_at_k: float
    n: int


@dataclass
class MetricRow:
    """A single metric value from an experiment run."""

    metric: str  # MetricName value
    value: float
    n: int  # sample size (0 if metric is not rate-based)
    resolution: str = ""  # Resolution value or "" for cross-resolution metrics
    baseline: str = ""  # "" for the main model, "hotspot" etc for baselines
    sweep_key: str = ""


@dataclass
class ExperimentResult:
    """Full output of one run_experiment() call."""

    run_id: str
    config_hash: str
    rows: list[MetricRow] = field(default_factory=list)
    status: str = "ok"  # "ok" | "failed"
    error: str = ""
