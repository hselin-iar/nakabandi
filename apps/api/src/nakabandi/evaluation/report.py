"""report.py — to_json() and to_markdown() for the Evaluation page (DOC 3 B7).

These are pure functions that take ExperimentResult objects and return formatted strings.
"""

from __future__ import annotations

import json
import math

from nakabandi.evaluation.config import ExperimentResult


def to_json(result: ExperimentResult, indent: int = 2) -> str:
    """Serialise an ExperimentResult to JSON.

    NaN metric values are represented as null in JSON.
    """
    d = {
        "run_id": result.run_id,
        "config_hash": result.config_hash,
        "status": result.status,
        "error": result.error,
        "rows": [
            {
                "metric": row.metric,
                "value": None if math.isnan(row.value) else row.value,
                "n": row.n,
                "resolution": row.resolution,
                "baseline": row.baseline,
                "sweep_key": row.sweep_key,
            }
            for row in result.rows
        ],
    }
    return json.dumps(d, indent=indent, ensure_ascii=False)


def to_markdown(result: ExperimentResult) -> str:
    """Format an ExperimentResult as a Markdown table for the README / Evaluation page."""
    lines: list[str] = [
        f"## Experiment Run `{result.run_id}`",
        f"- **Status**: {result.status}",
        f"- **Config hash**: `{result.config_hash}`",
    ]
    if result.error:
        lines.append(f"- **Error**: {result.error}")

    if not result.rows:
        lines.append("\n_No metric rows._")
        return "\n".join(lines)

    lines.append("\n| metric | value | n | resolution | baseline | sweep_key |")
    lines.append("|---|---|---|---|---|---|")
    for row in result.rows:
        v = "NaN" if math.isnan(row.value) else f"{row.value:.4f}"
        lines.append(
            f"| {row.metric} | {v} | {row.n} | {row.resolution} | {row.baseline or '(model)'} | {row.sweep_key} |"  # noqa: E501
        )
    return "\n".join(lines)


def results_to_markdown(results: list[ExperimentResult]) -> str:
    """Format a list of ExperimentResult objects (sweep output) as Markdown."""
    parts = [to_markdown(r) for r in results]
    return "\n\n---\n\n".join(parts)
