"""sweeps.py — expand_grid() and run_sweep() (DOC 3 B7).

expand_grid produces one ExperimentConfig per cell of the parameter grid.
run_sweep runs each cell sequentially, continues past failures, and reports them.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from nakabandi.evaluation.config import ExperimentConfig, ExperimentResult, SweepGrid

logger = logging.getLogger(__name__)


def expand_grid(base: ExperimentConfig, grid: SweepGrid | None = None) -> list[ExperimentConfig]:
    """Return one ExperimentConfig per cell of the sweep grid.

    Each cell overrides (timing_median_min, channel_mix, locality) on base_config.
    sweep_key is set to "tm={tm}|mix={mix}|loc={loc}" for display.
    """
    if grid is None:
        grid = SweepGrid()
    configs: list[ExperimentConfig] = []
    for tm in grid.timing_medians_min:
        for mix in grid.channel_mixes:
            for loc in grid.localities:
                key = f"tm={tm}|mix={mix}|loc={loc}"
                cfg = ExperimentConfig(
                    seed=base.seed,
                    days_history=base.days_history,
                    days_test=base.days_test,
                    n_clusters=base.n_clusters,
                    n_per_day=base.n_per_day,
                    timing_median_min=tm,
                    channel_mix=mix,
                    locality=loc,
                    top_k=base.top_k,
                    oracle_url=base.oracle_url,
                    model_store_dir=base.model_store_dir,
                    sweep_key=key,
                )
                configs.append(cfg)
    return configs


def run_sweep(
    configs: list[ExperimentConfig],
    runner: Callable[[ExperimentConfig], ExperimentResult] | None = None,
) -> list[ExperimentResult]:
    """Run each config sequentially; continue past failures; report all results.

    Args:
        configs: list of ExperimentConfig cells from expand_grid().
        runner:  callable that runs one experiment; defaults to run_experiment().
                 Injected for testing.

    Returns list of ExperimentResult, one per config (failed cells have status="failed").
    """
    if runner is None:
        from nakabandi.evaluation.runner import run_experiment

        runner = run_experiment

    results: list[ExperimentResult] = []
    n = len(configs)
    for i, cfg in enumerate(configs, start=1):
        logger.info("sweep cell %d/%d sweep_key=%s", i, n, cfg.sweep_key)
        result = runner(cfg)
        results.append(result)
        if result.status == "failed":
            logger.warning(
                "sweep cell %d/%d FAILED sweep_key=%s error=%s",
                i,
                n,
                cfg.sweep_key,
                result.error,
            )
    return results
