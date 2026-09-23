"""Public facade of the evaluation module (DOC 3 Evaluation Harness B7).

ISOLATION RULES (enforced by import-linter):
  - Only this module may import OracleClient.
  - main.py may NEVER import nakabandi.evaluation.
  - No other module may import nakabandi.evaluation.** directly (only the facade).

Exported API:
  run_experiment(cfg)        → ExperimentResult
  expand_grid(base, grid)    → list[ExperimentConfig]
  run_sweep(configs, runner) → list[ExperimentResult]
  load_results(session)      → list[ExperimentResult]
  to_json(result)            → str
  to_markdown(result)        → str
"""

from __future__ import annotations

from nakabandi.evaluation.config import (
    BinStat,
    CurvePoint,
    ExperimentConfig,
    ExperimentResult,
    LeadTimeStats,
    MetricRow,
    ShareStats,
    SweepGrid,
)
from nakabandi.evaluation.report import results_to_markdown, to_json, to_markdown
from nakabandi.evaluation.runner import run_experiment
from nakabandi.evaluation.store import ExperimentMetricRepo, ExperimentRunRepo
from nakabandi.evaluation.sweeps import expand_grid, run_sweep

__all__ = [
    # Config
    "ExperimentConfig",
    "SweepGrid",
    "ExperimentResult",
    "MetricRow",
    "BinStat",
    "LeadTimeStats",
    "ShareStats",
    "CurvePoint",
    # Core entry points
    "run_experiment",
    "expand_grid",
    "run_sweep",
    # Persistence
    "ExperimentRunRepo",
    "ExperimentMetricRepo",
    # Reports
    "to_json",
    "to_markdown",
    "results_to_markdown",
]


def load_results(session: object) -> list[ExperimentResult]:
    """Return all experiment runs (without metric rows) newest-first."""
    repo = ExperimentRunRepo(session)  # type: ignore[arg-type]
    return repo.list_all()
