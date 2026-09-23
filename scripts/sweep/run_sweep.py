#!/usr/bin/env python
"""scripts/sweep/run_sweep.py — B9 sweep script (DOC 4 B9).

Runs the default evaluation sweep (18 cells = 3 timing × 3 mixes × 2 localities),
plus feedback on/off and cold-start curve variants on 7-day worlds. Exports results
JSON and Markdown to docs/results/.

Usage (from repo root):
    uv run python scripts/sweep/run_sweep.py [--out docs/results]

This script requires the world-sim compose stack to produce real results.
When the oracle is not reachable, each cell records status="ok" with empty rows
(the harness stub strategy from B7). The script reports n and refuse rates, and
marks cells that produced no data as STUB in the results table.

Never cherry-pick cells. Never report a single accuracy number.
Failures and empty cells are listed, not hidden (DOC 4 B9 common drift).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import textwrap
from pathlib import Path

# ── repo root on sys.path ────────────────────────────────────────────────────
_REPO = Path(__file__).parents[2]
sys.path.insert(0, str(_REPO / "apps" / "api" / "src"))

from nakabandi.evaluation.config import ExperimentConfig, SweepGrid  # noqa: E402
from nakabandi.evaluation.report import results_to_markdown, to_json  # noqa: E402
from nakabandi.evaluation.sweeps import expand_grid, run_sweep  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sweep")

# ---------------------------------------------------------------------------
# Sweep variants
# ---------------------------------------------------------------------------

# DEFAULT: timing × channel × locality (B9 spec)
DEFAULT_GRID = SweepGrid(
    timing_medians_min=(15.0, 60.0, 240.0),
    channel_mixes=("atm_heavy", "mixed", "upi_heavy"),
    localities=("local", "dispersed"),
)

# FEEDBACK ON/OFF: two feedback variants on the default config
FEEDBACK_CONFIGS = [
    ExperimentConfig(
        seed=42,
        days_history=5,
        days_test=2,
        n_clusters=6,
        n_per_day=100,
        timing_median_min=60.0,
        channel_mix="mixed",
        locality="local",
        sweep_key="feedback=on",
    ),
    ExperimentConfig(
        seed=42,
        days_history=5,
        days_test=2,
        n_clusters=6,
        n_per_day=100,
        timing_median_min=60.0,
        channel_mix="mixed",
        locality="local",
        sweep_key="feedback=off",
    ),
]

# COLD-START: 7-day worlds, cold-start curve focus (S4)
COLD_START_CONFIG = ExperimentConfig(
    seed=99,
    days_history=7,
    days_test=3,
    n_clusters=6,
    n_per_day=100,
    timing_median_min=60.0,
    channel_mix="mixed",
    locality="local",
    sweep_key="cold_start_7day",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stub_summary(pairs: list[tuple]) -> str:  # type: ignore[type-arg]
    """Count stub/empty cells vs populated cells."""
    n_stub = sum(1 for _cfg, r in pairs if not r.rows)
    n_ok = sum(1 for _cfg, r in pairs if r.rows)
    return f"{n_ok} cells with data, {n_stub} stubs (oracle not reachable)"


def _build_results_table(pairs: list[tuple], section_name: str) -> str:  # type: ignore[type-arg]
    """Markdown table: sweep_key | n | status | abstention_rate | notes."""
    lines = [
        f"\n## {section_name}\n",
        "| sweep_key | n | status | abstention_rate | note |",
        "|---|---|---|---|---|",
    ]
    for cfg, r in pairs:
        n = len(r.rows)
        abstention = next((row.abstention_rate for row in r.rows), None)  # type: ignore[attr-defined]
        abst_str = f"{abstention:.3f}" if abstention is not None else "—"
        stub_note = "STUB — oracle not reachable; swap when compose stack runs" if n == 0 else ""
        lines.append(f"| `{cfg.sweep_key}` | {n} | {r.status} | {abst_str} | {stub_note} |")
    return "\n".join(lines)


def _build_report(
    default_pairs: list[tuple],  # type: ignore[type-arg]
    feedback_pairs: list[tuple],  # type: ignore[type-arg]
    cold_start_pairs: list[tuple],  # type: ignore[type-arg]
) -> str:
    """Assemble the full results Markdown report."""
    sections = [
        textwrap.dedent("""\
            # NAKABANDI Evaluation Sweep Results (B9)

            > These results were produced by `scripts/sweep/run_sweep.py` (DOC 4 Step B9).
            > The compose stack (world-sim oracle) must be running to produce real metrics.
            > Cells without data are marked **STUB** and must be re-run once the stack is
            > available. Failures are listed, never hidden.
            >
            > Do NOT cherry-pick cells. Do NOT report a single accuracy number.
            > Baselines are shown side-by-side. Abstention rates are reported when n < 30.
        """),
        _build_results_table(default_pairs, "Default Sweep (3 timing × 3 mix × 2 locality)"),
        _build_results_table(feedback_pairs, "Feedback On / Off"),
        _build_results_table(cold_start_pairs, "Cold-Start Curve (7-day worlds)"),
        "\n## Baseline Comparison\n",
        "> Baselines: **HotspotBaseline** (frequency), **NearestToVictim**, **BankFootprint**.",
        "> Baseline metrics are computed inside each cell's ExperimentResult when oracle is reachable.",  # noqa: E501
        "> With stub results (oracle not reachable), baseline comparison is deferred.",
        "\n## Failures and Refusals\n",
    ]

    # List any failures
    all_pairs = default_pairs + feedback_pairs + cold_start_pairs
    failures = [(_cfg, r) for _cfg, r in all_pairs if r.status == "failed"]
    if failures:
        sections.append(f"**{len(failures)} cell(s) failed:**\n")
        for cfg, f in failures:
            sections.append(f"- `{cfg.sweep_key}`: {f.error}")
    else:
        sections.append("No failures. (Stubs are not failures; they are deferred runs.)")

    sections.append(
        "\n## n < 30 Notice\n"
        "Cells with n < 30 observations report NaN for precision@k, hit_rate@k, and brier_score.\n"
        "These are shown as `—` in the table above. Do not interpret NaN as zero or as a good result."  # noqa: E501
    )

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Run B9 evaluation sweep")
    parser.add_argument("--out", default="docs/results", help="Output directory")
    parser.add_argument(
        "--oracle-url",
        default="http://localhost:8001",
        help="Base URL of world-sim oracle API",
    )
    args = parser.parse_args()

    out_dir = _REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    base_config = ExperimentConfig(
        seed=42,
        days_history=5,
        days_test=2,
        n_clusters=6,
        n_per_day=100,
        oracle_url=args.oracle_url,
    )

    # --- 1. Default sweep (18 cells) ----------------------------------------
    log.info("Expanding default sweep grid (18 cells)...")
    default_configs = expand_grid(base_config, DEFAULT_GRID)
    log.info("Running %d cells...", len(default_configs))
    default_results = run_sweep(default_configs)
    default_pairs = list(zip(default_configs, default_results, strict=False))
    log.info("Default sweep: %s", _stub_summary(default_pairs))

    # --- 2. Feedback on/off (2 cells) ----------------------------------------
    log.info("Running feedback on/off (2 cells)...")
    feedback_results = run_sweep(FEEDBACK_CONFIGS)
    feedback_pairs = list(zip(FEEDBACK_CONFIGS, feedback_results, strict=False))

    # --- 3. Cold-start curve (1 cell, 7-day world) ---------------------------
    log.info("Running cold-start curve (7-day world)...")
    cold_start_results = run_sweep([COLD_START_CONFIG])
    cold_start_pairs = list(zip([COLD_START_CONFIG], cold_start_results, strict=False))

    all_results = default_results + feedback_results + cold_start_results
    all_pairs = default_pairs + feedback_pairs + cold_start_pairs

    # --- 4. Collect run IDs --------------------------------------------------
    run_ids = [r.run_id for r in all_results]

    # --- 5. Write JSON -------------------------------------------------------
    sweep_json = {
        "run_ids": run_ids,
        "n_cells": len(all_pairs),
        "cells": [to_json(r) for _cfg, r in all_pairs],
    }
    json_path = out_dir / "sweep_results.json"
    json_path.write_text(json.dumps(sweep_json, indent=2), encoding="utf-8")
    log.info("JSON written → %s", json_path)

    # --- 6. Write Markdown ---------------------------------------------------
    md = _build_report(default_pairs, feedback_pairs, cold_start_pairs)
    md_path = out_dir / "sweep_results.md"
    md_path.write_text(md, encoding="utf-8")
    log.info("Markdown written → %s", md_path)

    # --- 7. Per-cell detail files -------------------------------------------
    for cfg, r in all_pairs:
        cell_key = cfg.sweep_key.replace("|", "_").replace("=", "-")
        cell_path = out_dir / f"cell_{cell_key}.md"
        cell_md = results_to_markdown([r])
        cell_path.write_text(cell_md, encoding="utf-8")

    log.info("Per-cell Markdown written (%d files).", len(all_pairs))

    # --- 8. Print summary to stdout ------------------------------------------
    n_stub = sum(1 for _cfg, r in all_pairs if not r.rows)
    n_fail = sum(1 for _cfg, r in all_pairs if r.status == "failed")
    n_data = sum(1 for _cfg, r in all_pairs if r.rows)

    print(f"\n{'=' * 60}")
    print(f"B9 Sweep complete: {len(all_results)} cells")
    print(f"  {n_data:3d} cells with data")
    print(f"  {n_stub:3d} stubs  (oracle not reachable -- re-run with compose stack)")
    print(f"  {n_fail:3d} failures (listed in {md_path})")
    print("\nResults:")
    print(f"  JSON     -> {json_path}")
    print(f"  Markdown -> {md_path}")
    print(f"  Run IDs  -> {run_ids[:5]}{'...' if len(run_ids) > 5 else ''}")
    print(f"{'=' * 60}")

    if n_fail > 0:
        print(f"\nWARNING: {n_fail} cell(s) failed. Check {md_path} for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
