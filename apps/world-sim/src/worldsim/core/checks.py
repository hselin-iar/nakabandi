"""checks.py — compare_to_public(world_summary, anchors) -> CheckReport (DOC 3 M1).

Compares the generated world's summary statistics against the public anchors
(data/anchors/public_anchors.json). Reports BOTH matches and mismatches. Never
raises on mismatch — all findings go in the report.

Usage:
    from worldsim.core.checks import compare_to_public, WorldSummary
    report = compare_to_public(summary, anchors)
    print(report.to_markdown())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Input: WorldSummary (caller computes from generated events)
# ---------------------------------------------------------------------------


@dataclass
class WorldSummary:
    """Aggregate statistics from one generated run — caller computes these."""

    complaints_per_day: float
    mean_amount_inr: float
    state_weights: dict[str, float]  # normalised fractions


# ---------------------------------------------------------------------------
# Output: CheckReport
# ---------------------------------------------------------------------------


@dataclass
class CheckItem:
    key: str
    anchor_value: Any
    generated_value: Any
    status: str  # "MATCH" | "MISMATCH" | "NO_ANCHOR"
    note: str


@dataclass
class CheckReport:
    items: list[CheckItem] = field(default_factory=list)

    @property
    def n_matches(self) -> int:
        return sum(1 for i in self.items if i.status == "MATCH")

    @property
    def n_mismatches(self) -> int:
        return sum(1 for i in self.items if i.status == "MISMATCH")

    @property
    def n_no_anchor(self) -> int:
        return sum(1 for i in self.items if i.status == "NO_ANCHOR")

    def to_markdown(self) -> str:
        lines = [
            "# Public Anchor Check Report\n",
            f"Matches: **{self.n_matches}** | Mismatches: **{self.n_mismatches}**"
            f" | No anchor: **{self.n_no_anchor}**\n",
            "| key | anchor | generated | status | note |",
            "|---|---|---|---|---|",
        ]
        for item in self.items:
            anchor_str = str(item.anchor_value) if item.anchor_value is not None else "—"
            lines.append(
                f"| `{item.key}` | {anchor_str} | {item.generated_value}"
                f" | **{item.status}** | {item.note} |"
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_matches": self.n_matches,
            "n_mismatches": self.n_mismatches,
            "n_no_anchor": self.n_no_anchor,
            "items": [
                {
                    "key": i.key,
                    "anchor_value": i.anchor_value,
                    "generated_value": i.generated_value,
                    "status": i.status,
                    "note": i.note,
                }
                for i in self.items
            ],
        }


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------

_COMPLAINTS_PER_DAY_RANGE_KEY = "load.complaints_per_day"
_AMOUNTS_MEAN_INR_KEY = "amounts.mean_inr"
_STATE_WEIGHTS_KEY = "geo.state_weights"

# Tolerance: within ±30% of anchor value counts as MATCH (priors, not calibrated)
_RELATIVE_TOLERANCE = 0.30
# State weight tolerance: absolute difference ≤ 0.10 per state
_STATE_WEIGHT_ABS_TOL = 0.10


def _relative_match(generated: float, anchor: float, rtol: float = _RELATIVE_TOLERANCE) -> bool:
    if anchor == 0:
        return generated == 0
    return abs(generated - anchor) / abs(anchor) <= rtol


def _fmt_float(v: float, decimals: int = 1) -> str:
    return f"{v:.{decimals}f}"


# ---------------------------------------------------------------------------
# Main comparison function
# ---------------------------------------------------------------------------


def compare_to_public(summary: WorldSummary, anchors: dict[str, Any]) -> CheckReport:
    """Compare world summary stats to public anchors. Never raises on mismatch.

    Args:
        summary: WorldSummary computed from generated events.
        anchors: dict loaded from data/anchors/public_anchors.json.

    Returns:
        CheckReport with matches, mismatches, and no-anchor items.
        The caller is responsible for printing/recording the report.
    """
    items: list[CheckItem] = []

    # ------------------------------------------------------------------
    # 1. Complaints per day
    # ------------------------------------------------------------------
    cpd_anchor_block = anchors.get("load", {}).get("complaints_per_day", {})
    cpd_anchor: float | None = cpd_anchor_block.get("value")  # type: ignore[assignment]

    if cpd_anchor is None:
        items.append(
            CheckItem(
                key=_COMPLAINTS_PER_DAY_RANGE_KEY,
                anchor_value=None,
                generated_value=_fmt_float(summary.complaints_per_day),
                status="NO_ANCHOR",
                note="No verified anchor value; see Appendix A",
            )
        )
    elif _relative_match(summary.complaints_per_day, float(cpd_anchor)):
        items.append(
            CheckItem(
                key=_COMPLAINTS_PER_DAY_RANGE_KEY,
                anchor_value=cpd_anchor,
                generated_value=_fmt_float(summary.complaints_per_day),
                status="MATCH",
                note=f"Within ±{int(_RELATIVE_TOLERANCE * 100)}% of anchor",
            )
        )
    else:
        ratio = summary.complaints_per_day / float(cpd_anchor) if cpd_anchor else float("nan")
        items.append(
            CheckItem(
                key=_COMPLAINTS_PER_DAY_RANGE_KEY,
                anchor_value=cpd_anchor,
                generated_value=_fmt_float(summary.complaints_per_day),
                status="MISMATCH",
                note=f"Generated is {ratio:.2f}× anchor; check load config or note in README",
            )
        )

    # ------------------------------------------------------------------
    # 2. Mean amount (INR)
    # ------------------------------------------------------------------
    amt_anchor_block = anchors.get("amounts", {}).get("mean_inr", {})
    amt_anchor: float | None = amt_anchor_block.get("value")  # type: ignore[assignment]

    if amt_anchor is None:
        items.append(
            CheckItem(
                key=_AMOUNTS_MEAN_INR_KEY,
                anchor_value=None,
                generated_value=_fmt_float(summary.mean_amount_inr, 0),
                status="NO_ANCHOR",
                note="No anchor available",
            )
        )
    elif _relative_match(summary.mean_amount_inr, float(amt_anchor)):
        items.append(
            CheckItem(
                key=_AMOUNTS_MEAN_INR_KEY,
                anchor_value=amt_anchor,
                generated_value=_fmt_float(summary.mean_amount_inr, 0),
                status="MATCH",
                note=f"Within ±{int(_RELATIVE_TOLERANCE * 100)}% of anchor",
            )
        )
    else:
        ratio = summary.mean_amount_inr / float(amt_anchor) if amt_anchor else float("nan")
        items.append(
            CheckItem(
                key=_AMOUNTS_MEAN_INR_KEY,
                anchor_value=amt_anchor,
                generated_value=_fmt_float(summary.mean_amount_inr, 0),
                status="MISMATCH",
                note=f"Generated is {ratio:.2f}× anchor; check amounts config",
            )
        )

    # ------------------------------------------------------------------
    # 3. State weights
    # ------------------------------------------------------------------
    sw_anchor_block = anchors.get("geo", {}).get("state_weights", {})
    sw_anchor: dict[str, float] | None = sw_anchor_block.get("value")  # type: ignore[assignment]

    if sw_anchor is None:
        items.append(
            CheckItem(
                key=_STATE_WEIGHTS_KEY,
                anchor_value=None,
                generated_value=str(summary.state_weights),
                status="NO_ANCHOR",
                note="No state weights anchor available",
            )
        )
    else:
        all_states = set(sw_anchor.keys()) | set(summary.state_weights.keys())
        for state in sorted(all_states):
            anchor_w = sw_anchor.get(state, 0.0)
            generated_w = summary.state_weights.get(state, 0.0)
            abs_diff = abs(generated_w - anchor_w)
            status = "MATCH" if abs_diff <= _STATE_WEIGHT_ABS_TOL else "MISMATCH"
            items.append(
                CheckItem(
                    key=f"{_STATE_WEIGHTS_KEY}.{state}",
                    anchor_value=f"{anchor_w:.3f}",
                    generated_value=f"{generated_w:.3f}",
                    status=status,
                    note=(
                        f"abs diff {abs_diff:.3f} ≤ {_STATE_WEIGHT_ABS_TOL}"
                        if status == "MATCH"
                        else f"abs diff {abs_diff:.3f} > {_STATE_WEIGHT_ABS_TOL}; review geo.state_weights"  # noqa: E501
                    ),
                )
            )

    return CheckReport(items=items)
