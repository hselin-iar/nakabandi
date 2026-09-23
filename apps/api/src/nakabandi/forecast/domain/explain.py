"""explain.py — rule-based evidence statements for a forecast (DOC 3 M2).

explain(ctx, ranked_location_ids, policy) -> list[EvidenceStatement]
    Generates human-readable evidence codes for the top candidate reasons.
    Each statement has a stable `code` (for S5 localisation), `params`, and `text_en`.
"""

from __future__ import annotations

from nakabandi.forecast.domain.types import (
    Candidate,
    ClusterContext,
    EvidenceStatement,
    FeatureRow,
)
from nakabandi.shared import Policy

# ---------------------------------------------------------------------------
# Evidence codes (stable; S5 will localise from code + params)
# ---------------------------------------------------------------------------
_CODE_PRIOR_CASHOUTS = "PRIOR_CASHOUTS_AT_LOCATION"
_CODE_SAME_BANK = "SAME_BANK_MATCH"
_CODE_CLUSTER_HISTORY = "CLUSTER_HISTORY_CELL"
_CODE_NEAR_HOME = "NEAR_VICTIM_HOME"
_CODE_NEAR_CENTROID = "NEAR_CLUSTER_CENTROID"
_CODE_NOVEL_CLUSTER = "NOVEL_CLUSTER"
_CODE_WIDE_FORECAST = "WIDE_FORECAST"
_CODE_STALE = "TIMING_STALE"
_CODE_HIGH_ACTIVITY = "HIGH_ACTIVITY_LOCATION"


def explain(
    ctx: ClusterContext,
    top_candidates: list[Candidate],
    top_feature_rows: list[FeatureRow],
    policy: Policy,
) -> list[EvidenceStatement]:
    """Generate evidence statements for the forecast.

    Rules fire in priority order; at most 4 statements are returned.
    Each code appears at most once.
    """
    statements: list[EvidenceStatement] = []
    seen_codes: set[str] = set()

    def _add(code: str, params: dict[str, str], text_en: str) -> None:
        if code not in seen_codes and len(statements) < 4:
            seen_codes.add(code)
            statements.append(EvidenceStatement(code=code, params=params, text_en=text_en))

    # --- Novel cluster ---
    if ctx.cluster_id is None or ctx.unique_accounts == 0:
        _add(
            _CODE_NOVEL_CLUSTER,
            {},
            "This account has not appeared in known mule clusters before — "
            "forecast is wider and lower confidence.",
        )

    # --- Stale timing ---
    if ctx.elapsed_min > 0 and policy.forecast.stale_residual_mass > 0:
        _add(
            _CODE_STALE,
            {"elapsed_min": str(int(ctx.elapsed_min))},
            f"Complaint was reported {int(ctx.elapsed_min)} minutes after the event; "
            "timing window may have partially elapsed.",
        )

    # --- Prior cash-outs at top location ---
    if top_candidates:
        top_cand = top_candidates[0]
        top_row = top_feature_rows[0]
        loc_count = int(ctx.cashout_location_counts.get(top_cand.location_id, 0))
        if loc_count > 0:
            _add(
                _CODE_PRIOR_CASHOUTS,
                {"location_id": top_cand.location_id, "count": str(loc_count)},
                f"This cluster has made {loc_count} prior cash-out(s)"
                " at the top forecast location.",
            )

        # --- Same bank match ---
        if top_row.same_bank > 0.5:
            _add(
                _CODE_SAME_BANK,
                {"location_id": top_cand.location_id},
                "The top forecast location belongs to the same bank as the victim's account.",
            )

        # --- Near home ---
        if top_cand.distance_to_home_km < 2.0:
            _add(
                _CODE_NEAR_HOME,
                {"dist_km": f"{top_cand.distance_to_home_km:.1f}"},
                f"The top forecast location is {top_cand.distance_to_home_km:.1f} km from "
                "the victim's home branch.",
            )

        # --- Near centroid ---
        if ctx.centroid_lat is not None and top_cand.distance_to_centroid_km < 3.0:
            _add(
                _CODE_NEAR_CENTROID,
                {"dist_km": f"{top_cand.distance_to_centroid_km:.1f}"},
                f"The top forecast location is {top_cand.distance_to_centroid_km:.1f} km from "
                "this cluster's known operational centre.",
            )

        # --- High activity ---
        if top_cand.activity_index > 0.7:
            _add(
                _CODE_HIGH_ACTIVITY,
                {"location_id": top_cand.location_id},
                "The top forecast location is a high-activity point in the registry.",
            )

    # --- Cluster cell history ---
    if ctx.cashout_cell_counts:
        top_cell_count = max(ctx.cashout_cell_counts.values())
        if top_cell_count > 0:
            _add(
                _CODE_CLUSTER_HISTORY,
                {"count": str(top_cell_count)},
                f"This cluster has {top_cell_count} prior cash-out(s) in the predicted cell.",
            )

    return statements
