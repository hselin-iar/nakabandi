"""ledger.py — AssumptionLedger (DOC 3 M1, DOC 2 Appendix A).

AssumptionLedger.build(cfg) -> LedgerDoc

One row per config key. Exported as Markdown and JSON with every run.
Tag: verified | derived | assumed | swept
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Literal

from worldsim.core.config import SimConfig

Tag = Literal["verified", "derived", "assumed", "swept"]


@dataclass
class LedgerRow:
    key: str
    value: object
    tag: Tag
    source: str
    confidence: str


@dataclass
class LedgerDoc:
    rows: list[LedgerRow] = field(default_factory=list)

    # -----------------------------------------------------------------------
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(
            {"rows": [asdict(r) for r in self.rows]},
            indent=indent,
            ensure_ascii=False,
            default=str,
        )

    def to_markdown(self) -> str:
        lines = [
            "# Assumption Ledger\n",
            "| key | value | tag | source | confidence |",
            "|---|---|---|---|---|",
        ]
        for r in self.rows:
            lines.append(f"| `{r.key}` | {r.value} | {r.tag} | {r.source} | {r.confidence} |")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


class AssumptionLedger:
    """Build an AssumptionLedger from a SimConfig.

    Completeness requirement (Done When): every key in sim.default.yaml appears
    exactly once. Tested by test_ledger_completeness().
    """

    @staticmethod
    def build(cfg: SimConfig) -> LedgerDoc:
        rows: list[LedgerRow] = []

        def row(key: str, value: object, tag: Tag, source: str, confidence: str) -> None:
            rows.append(
                LedgerRow(key=key, value=value, tag=tag, source=source, confidence=confidence)
            )

        # seed
        row("seed", cfg.seed, "assumed", "Run parameter; user-supplied", "n/a")

        # world
        row("world.days", cfg.world.days, "assumed", "Run parameter", "n/a")
        row("world.n_clusters", cfg.world.n_clusters, "assumed", "Run parameter; swept", "low")

        # load
        row(
            "load.complaints_per_day",
            cfg.load.complaints_per_day,
            "derived",
            "I4C 2025: ~24.1 lakh/year ÷ 365 ≈ 6,600/day national; golden uses district slice ~600",
            "high_order_of_magnitude",
        )

        # amounts
        row(
            "amounts.mean_paise",
            cfg.amounts.mean_paise,
            "verified",
            "NCRB 2024 / CERT-In: ≈₹94,000 mean (2025); ₹1.19 lakh (2024)",
            "high_for_mean",
        )
        row(
            "amounts.shape_sigma",
            cfg.amounts.shape_sigma,
            "assumed",
            "Lognormal shape; heavy-tailed assumption; not published",
            "low",
        )

        # network
        row(
            "network.layers_min",
            cfg.network.layers_min,
            "verified",
            "Case-based: minimum 2 (victim → layer-1 mule)",
            "medium_low",
        )
        row(
            "network.layers_max",
            cfg.network.layers_max,
            "verified",
            "Case-based: observed up to 12 hop layers",
            "medium_low",
        )
        row(
            "network.layers_median",
            cfg.network.layers_median,
            "derived",
            "Approximate median ~4 from case files; not a distribution study",
            "medium_low",
        )
        row(
            "network.accounts_per_cluster",
            cfg.network.accounts_per_cluster,
            "derived",
            "Appendix A: 10 to ~20,000, median ~100; swept",
            "low_medium",
        )
        row(
            "network.bridge_rate",
            cfg.network.bridge_rate,
            "assumed",
            "Assumed small share of accounts used by two clusters; exercises union-find",
            "none",
        )
        row(
            "network.hop_visibility",
            cfg.network.hop_visibility,
            "assumed",
            "Share of deeper hops traced later; assumption; swept",
            "none",
        )

        # caps
        row(
            "caps.card_atm_daily_inr",
            cfg.caps.card_atm_daily_inr,
            "verified",
            "Bank-specific published limits; range 20,000–1,00,000; no universal RBI cap",
            "medium",
        )
        row(
            "caps.cardless_atm_txn_inr",
            cfg.caps.cardless_atm_txn_inr,
            "verified",
            "RBI/Bank notifications on cardless ATM transaction limits (~₹10,000)",
            "medium",
        )
        row(
            "caps.aeps_txn_inr",
            cfg.caps.aeps_txn_inr,
            "verified",
            "NPCI AEPS guidelines: ~₹10,000 per transaction",
            "medium_low",
        )
        row(
            "caps.aeps_daily_inr",
            cfg.caps.aeps_daily_inr,
            "verified",
            "NPCI AEPS guidelines: daily limit 10,000–50,000 (bank-specific)",
            "medium_low",
        )

        # timing (each component)
        for i, comp in enumerate(cfg.timing.mixture):
            prefix = f"timing.mixture[{i}]"
            row(
                f"{prefix}.weight",
                comp.weight,
                "assumed",
                "Proportion unknown; swept; not calibrated",
                "low",
            )
            row(
                f"{prefix}.component",
                comp.component,
                "assumed",
                "Two-component structure assumed from fast/slow pattern",
                "low",
            )
            row(
                f"{prefix}.lognormal_median_min",
                comp.lognormal_median_min,
                "swept",
                "Appendix A: fast range 1–60 min; slow hours to a day; SWEEP 15/60/240",
                "low",
            )
            row(
                f"{prefix}.lognormal_sigma",
                comp.lognormal_sigma,
                "assumed",
                "Shape parameter; assumed; not published",
                "none",
            )

        # channels
        for channel, weight in cfg.channels.mix.items():
            row(
                f"channels.mix.{channel}",
                weight,
                "assumed",
                "Unpublished; three labelled-illustrative mixes; NOT an estimate",
                "none",
            )

        # footprint
        row(
            "footprint.locality",
            cfg.footprint.locality,
            "swept",
            "Unpublished; swept from local (district) to dispersed (multi-state)",
            "none",
        )
        row(
            "footprint.size_per_cluster",
            cfg.footprint.size_per_cluster,
            "swept",
            "Appendix A: one hotspot report cites ~5,000 ATM IDs; sweep tens to hundreds",
            "low",
        )

        # mule
        row(
            "mule.lifetime_days",
            cfg.mule.lifetime_days,
            "assumed",
            "Appendix A: 1 to 180, median ~30; wide sweep",
            "low",
        )

        # geo
        for state, weight in cfg.geo.state_weights.items():
            row(
                f"geo.state_weights.{state}",
                weight,
                "verified",
                "MHA Lok Sabha UQ 1906, 11 Mar 2025 — state-wise cybercrime complaint counts (normalised)",  # noqa: E501
                "medium",
            )

        # kit
        row(
            "kit.cards_per_account",
            cfg.kit.cards_per_account,
            "verified",
            "Reported kits hold one ATM card per account; cap-driven repeat visits",
            "low",
        )

        # noise
        row(
            "noise.innocent_layer1_rate",
            cfg.noise.innocent_layer1_rate,
            "assumed",
            "Assumed 2–5% of complaints on innocent holders; makes false-hold metric non-vacuous; swept",  # noqa: E501
            "none",
        )

        # lag
        row(
            "lag.min",
            cfg.lag.min,
            "assumed",
            "Bank/police confirmation lag; minimum hours to days; assumption",
            "none",
        )
        row(
            "lag.median",
            cfg.lag.median,
            "assumed",
            "Bank/police confirmation lag; median ~6 h; assumption; swept",
            "none",
        )
        row(
            "lag.max",
            cfg.lag.max,
            "assumed",
            "Bank/police confirmation lag; maximum up to 48 h; assumption",
            "none",
        )

        return LedgerDoc(rows=rows)
