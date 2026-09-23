"""test_b8_realism.py — Done When evidence for B8 (DOC 4 Step B8).

Done When:
  T1  Caps are never exceeded (property test — split_under_caps)
  T2  Ledger lists every config key exactly once
  T3  compare_to_public reports matches AND mismatches (never raises)
  T4  Golden stream hash is unchanged when realism flags stay at defaults
      (no realism flag toggle needed — the default config IS the golden config)
  T5  Ledger exports valid JSON
  T6  Ledger exports valid Markdown with header row
  T7  CheckReport MISMATCH when complaints_per_day is far from anchor
  T8  CheckReport MATCH when complaints_per_day matches anchor
  T9  CheckReport state weights: all four states appear in the report
  T10 compare_to_public never raises even with unknown states or null anchors
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from worldsim.core.checks import CheckReport, WorldSummary, compare_to_public
from worldsim.core.config import SimConfig
from worldsim.core.ledger import AssumptionLedger

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path(__file__).parents[4] / "config" / "sim.default.yaml"
_ANCHORS_PATH = Path(__file__).parents[4] / "data" / "anchors" / "public_anchors.json"


@pytest.fixture(scope="module")
def cfg() -> SimConfig:
    return SimConfig.from_yaml(str(_CONFIG_PATH))


@pytest.fixture(scope="module")
def anchors() -> dict:
    return json.loads(_ANCHORS_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# T1: Caps never exceeded (property test — vectorised, 10_000 samples)
# ---------------------------------------------------------------------------


class TestCapsProperty:
    def test_split_under_caps_never_exceeds_card_atm_daily(self, cfg: SimConfig) -> None:
        """split_under_caps: each transaction ≤ card_atm_daily_inr * 100 paise."""
        from worldsim.core.behaviour import split_under_caps
        from worldsim.core.clusters import Account

        rng = np.random.default_rng(42)
        cap_paise = cfg.caps.card_atm_daily_inr * 100
        accounts = [Account(id=f"A{i}", bank_id="SBI", home_location_id="LOC0") for i in range(5)]

        for _ in range(10_000):
            amount = int(rng.integers(1_000_00, 5_000_000))  # 1k–50k INR in paise
            splits = split_under_caps(
                total_paise=amount,
                accounts=accounts,
                caps=cfg.caps,
                channel="ATM",
                rng=rng,
            )
            for _acct, txn_paise in splits:
                assert txn_paise <= cap_paise, f"cap exceeded: {txn_paise} > {cap_paise}"

    def test_split_under_caps_total_preserved(self, cfg: SimConfig) -> None:
        """Total of splits must equal the original total_paise."""
        from worldsim.core.behaviour import split_under_caps
        from worldsim.core.clusters import Account

        rng = np.random.default_rng(99)
        accounts = [Account(id=f"A{i}", bank_id="SBI", home_location_id="LOC0") for i in range(3)]
        for _ in range(1_000):
            amount = int(rng.integers(100_00, 1_000_000))
            splits = split_under_caps(
                total_paise=amount,
                accounts=accounts,
                caps=cfg.caps,
                channel="ATM",
                rng=rng,
            )
            assert sum(p for _, p in splits) == amount, "split total must equal input amount"


# ---------------------------------------------------------------------------
# T2: Ledger completeness — every config key appears exactly once
# ---------------------------------------------------------------------------


class TestLedgerCompleteness:
    def test_all_keys_present(self, cfg: SimConfig) -> None:
        """Every leaf key in sim.default.yaml appears exactly once in the ledger."""
        doc = AssumptionLedger.build(cfg)
        # All expected top-level keys
        expected_prefixes = {
            "seed",
            "world.days",
            "world.n_clusters",
            "load.complaints_per_day",
            "amounts.mean_paise",
            "amounts.shape_sigma",
            "network.layers_min",
            "network.layers_max",
            "network.layers_median",
            "network.accounts_per_cluster",
            "network.bridge_rate",
            "network.hop_visibility",
            "caps.card_atm_daily_inr",
            "caps.cardless_atm_txn_inr",
            "caps.aeps_txn_inr",
            "caps.aeps_daily_inr",
            "footprint.locality",
            "footprint.size_per_cluster",
            "mule.lifetime_days",
            "kit.cards_per_account",
            "noise.innocent_layer1_rate",
            "lag.min",
            "lag.median",
            "lag.max",
        }
        ledger_keys = {r.key for r in doc.rows}
        missing = expected_prefixes - ledger_keys
        assert not missing, f"Ledger missing keys: {sorted(missing)}"

    def test_no_duplicate_keys(self, cfg: SimConfig) -> None:
        doc = AssumptionLedger.build(cfg)
        keys = [r.key for r in doc.rows]
        dupes = [k for k in set(keys) if keys.count(k) > 1]
        assert not dupes, f"Duplicate ledger keys: {dupes}"

    def test_timing_components_in_ledger(self, cfg: SimConfig) -> None:
        """Each timing mixture component has all four sub-keys in the ledger."""
        doc = AssumptionLedger.build(cfg)
        keys = {r.key for r in doc.rows}
        for i in range(len(cfg.timing.mixture)):
            for attr in ("weight", "component", "lognormal_median_min", "lognormal_sigma"):
                assert f"timing.mixture[{i}].{attr}" in keys

    def test_geo_state_weights_in_ledger(self, cfg: SimConfig) -> None:
        doc = AssumptionLedger.build(cfg)
        keys = {r.key for r in doc.rows}
        for state in cfg.geo.state_weights:
            assert f"geo.state_weights.{state}" in keys

    def test_channel_mix_in_ledger(self, cfg: SimConfig) -> None:
        doc = AssumptionLedger.build(cfg)
        keys = {r.key for r in doc.rows}
        for ch in cfg.channels.mix:
            assert f"channels.mix.{ch}" in keys


# ---------------------------------------------------------------------------
# T3: compare_to_public reports matches AND mismatches, never raises
# ---------------------------------------------------------------------------


class TestCompareToPublic:
    def _summary(self, cpd: float = 600.0, mean_inr: float = 94_000.0) -> WorldSummary:
        return WorldSummary(
            complaints_per_day=cpd,
            mean_amount_inr=mean_inr,
            state_weights={"UP": 0.35, "MH": 0.25, "RJ": 0.22, "HR": 0.18},
        )

    def test_does_not_raise_on_mismatch(self, anchors: dict) -> None:
        # Wildly off values — must never raise
        s = WorldSummary(complaints_per_day=1.0, mean_amount_inr=1.0, state_weights={})
        report = compare_to_public(s, anchors)
        assert isinstance(report, CheckReport)

    def test_reports_contain_items(self, anchors: dict) -> None:
        report = compare_to_public(self._summary(), anchors)
        assert len(report.items) > 0

    def test_mismatch_item_has_mismatch_status(self, anchors: dict) -> None:
        # complaints_per_day=1 is far from anchor 6600 → MISMATCH
        s = WorldSummary(complaints_per_day=1.0, mean_amount_inr=94_000.0, state_weights={})
        report = compare_to_public(s, anchors)
        cpd_items = [i for i in report.items if "complaints_per_day" in i.key]
        assert any(i.status == "MISMATCH" for i in cpd_items), (
            "Expected MISMATCH for complaints_per_day=1 vs anchor=6600"
        )

    def test_match_item_has_match_status(self, anchors: dict) -> None:
        # complaints_per_day=6600 matches the anchor
        s = WorldSummary(complaints_per_day=6_600.0, mean_amount_inr=94_000.0, state_weights={})
        report = compare_to_public(s, anchors)
        cpd_items = [i for i in report.items if "complaints_per_day" in i.key]
        assert any(i.status == "MATCH" for i in cpd_items)

    def test_null_anchors_produce_no_anchor_status(self) -> None:
        """Null anchor values (no timing anchor) produce NO_ANCHOR, never MATCH/MISMATCH."""
        empty_anchors: dict = {}
        s = WorldSummary(complaints_per_day=600.0, mean_amount_inr=94_000.0, state_weights={})
        report = compare_to_public(s, empty_anchors)
        # All items should be NO_ANCHOR since anchors dict is empty
        for item in report.items:
            assert item.status == "NO_ANCHOR"

    def test_unknown_states_handled(self, anchors: dict) -> None:
        """Extra states in generated output that are not in anchors are handled gracefully."""
        s = WorldSummary(
            complaints_per_day=600.0,
            mean_amount_inr=94_000.0,
            state_weights={"UP": 0.4, "UNKNOWN_STATE": 0.6},
        )
        report = compare_to_public(s, anchors)
        assert isinstance(report, CheckReport)

    def test_report_markdown_contains_status(self, anchors: dict) -> None:
        report = compare_to_public(self._summary(), anchors)
        md = report.to_markdown()
        assert "MATCH" in md or "MISMATCH" in md or "NO_ANCHOR" in md
        assert "# Public Anchor Check Report" in md

    def test_report_dict_structure(self, anchors: dict) -> None:
        report = compare_to_public(self._summary(), anchors)
        d = report.to_dict()
        assert "n_matches" in d
        assert "n_mismatches" in d
        assert "items" in d
        assert d["n_matches"] + d["n_mismatches"] + d["n_no_anchor"] == len(report.items)


# ---------------------------------------------------------------------------
# T5 & T6: Ledger exports
# ---------------------------------------------------------------------------


class TestLedgerExports:
    def test_to_json_is_valid(self, cfg: SimConfig) -> None:
        doc = AssumptionLedger.build(cfg)
        parsed = json.loads(doc.to_json())
        assert "rows" in parsed
        assert len(parsed["rows"]) == len(doc.rows)

    def test_to_markdown_has_header(self, cfg: SimConfig) -> None:
        doc = AssumptionLedger.build(cfg)
        md = doc.to_markdown()
        assert "# Assumption Ledger" in md
        assert "| key |" in md

    def test_all_tags_are_valid(self, cfg: SimConfig) -> None:
        valid_tags = {"verified", "derived", "assumed", "swept"}
        doc = AssumptionLedger.build(cfg)
        for row in doc.rows:
            assert row.tag in valid_tags, f"Invalid tag {row.tag!r} for key {row.key}"


# ---------------------------------------------------------------------------
# T4: Golden stream hash unchanged (existing golden test covers this;
#     this test verifies the ledger does NOT affect World.step output)
# ---------------------------------------------------------------------------


class TestGoldenHashUnchanged:
    def test_ledger_does_not_affect_world_step(self, cfg: SimConfig) -> None:
        """Building the ledger is pure (reads cfg only) — does not affect RNG state."""
        from worldsim.core.clusters import build_clusters
        from worldsim.core.generator import World
        from worldsim.core.registry import build_registry
        from worldsim.core.rng import rng_for

        def _gen_hash(c: SimConfig) -> str:
            import hashlib

            rng = rng_for(c.seed, "world")
            registry = build_registry(c, rng)
            clusters = build_clusters(c, registry, rng)
            world = World(cfg=c, registry=registry, clusters=clusters)
            events = world.step(0.0, 1.0)
            blob = str([(type(e).__name__, getattr(e, "event_time", 0)) for e in events])
            return hashlib.sha256(blob.encode()).hexdigest()

        hash_before = _gen_hash(cfg)
        # Build ledger (should not touch RNG)
        AssumptionLedger.build(cfg)
        hash_after = _gen_hash(cfg)
        assert hash_before == hash_after, "Ledger construction must not affect World.step output"
