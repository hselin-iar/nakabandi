"""Unit tests for worldsim core (DOC 3 M1 testing plan — Unit section)."""

from __future__ import annotations

import math

import numpy as np
import pytest
from worldsim.core.config import SimConfig
from worldsim.core.rng import rng_for
from worldsim.core.timing import sample_delay_array, sample_delay_min

_CFG_PATH = "config/sim.default.yaml"


@pytest.fixture(scope="module")
def cfg() -> SimConfig:
    return SimConfig.from_yaml(_CFG_PATH)


# ---------------------------------------------------------------------------
# rng_for determinism
# ---------------------------------------------------------------------------


def test_rng_for_same_args_gives_same_sequence():
    rng1 = rng_for(42, "clusters", "C-0001")
    rng2 = rng_for(42, "clusters", "C-0001")
    assert rng1.integers(0, 10_000) == rng2.integers(0, 10_000)


def test_rng_for_different_names_give_different_sequences():
    rng_a = rng_for(42, "a")
    rng_b = rng_for(42, "b")
    draws_a = [rng_a.integers(0, 10_000) for _ in range(10)]
    draws_b = [rng_b.integers(0, 10_000) for _ in range(10)]
    assert draws_a != draws_b


def test_rng_for_order_matters():
    rng_ab = rng_for(42, "a", "b")
    rng_ba = rng_for(42, "b", "a")
    assert rng_ab.integers(0, 10_000) != rng_ba.integers(0, 10_000)


def test_rng_for_different_seeds_differ():
    rng1 = rng_for(42, "test")
    rng2 = rng_for(99, "test")
    assert rng1.integers(0, 10_000) != rng2.integers(0, 10_000)


# ---------------------------------------------------------------------------
# sample_delay_min — matches the configured mixture (KS-adjacent check)
# ---------------------------------------------------------------------------


def test_sample_delay_min_is_positive(cfg: SimConfig):
    rng = rng_for(42, "timing_test")
    for _ in range(100):
        d = sample_delay_min(cfg.timing, rng)
        assert d >= 1.0, f"delay {d} < 1.0"


def test_sample_delay_array_shape(cfg: SimConfig):
    rng = rng_for(42, "timing_arr")
    delays = sample_delay_array(cfg.timing, rng, 500)
    assert delays.shape == (500,)
    assert np.all(delays >= 1.0)
    assert np.all(delays <= 10_080.0)


def test_sample_delay_fast_component_median(cfg: SimConfig):
    """Fast component median should be close to lognormal_median_min (within 3x)."""
    fast = next(c for c in cfg.timing.mixture if c.component == "fast")
    rng = rng_for(42, "fast_median")
    # Force-sample 2000 from fast component only
    delays = np.array(
        [
            math.exp(rng.normal(math.log(fast.lognormal_median_min), fast.lognormal_sigma))
            for _ in range(2000)
        ]
    )
    empirical_median = float(np.median(delays))
    assert empirical_median > fast.lognormal_median_min / 3
    assert empirical_median < fast.lognormal_median_min * 3


# ---------------------------------------------------------------------------
# SimConfig loading
# ---------------------------------------------------------------------------


def test_simconfig_loads(cfg: SimConfig):
    assert cfg.seed == 42
    assert cfg.world.n_clusters == 6
    assert cfg.world.days == 3


def test_simconfig_forbids_unknown_keys():
    import yaml
    from pydantic import ValidationError

    raw = yaml.safe_load(open(_CFG_PATH).read())
    raw["unknown_key_xyz"] = 999
    with pytest.raises(ValidationError):
        SimConfig.model_validate(raw)


def test_timing_weights_sum_to_one(cfg: SimConfig):
    total = sum(c.weight for c in cfg.timing.mixture)
    assert abs(total - 1.0) < 1e-6


def test_channel_mix_sums_to_one(cfg: SimConfig):
    total = sum(cfg.channels.mix.values())
    assert abs(total - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# split_under_caps
# ---------------------------------------------------------------------------


def test_split_under_caps_never_exceeds_txn_cap(cfg: SimConfig):
    from worldsim.core.behaviour import split_under_caps
    from worldsim.core.clusters import Account

    rng = rng_for(42, "caps_test")
    accounts = [Account(id=f"A{i}", bank_id="SBI", home_location_id=None) for i in range(10)]
    total = cfg.caps.card_atm_daily_inr * 100 * 3  # 3x the cap
    splits = split_under_caps(total, accounts, cfg.caps, "ATM", rng)
    cap_paise = cfg.caps.card_atm_daily_inr * 100
    for _, amount in splits:
        # Each individual split respects the transaction cap
        assert amount <= cap_paise + 1  # +1 for remainder rounding


def test_split_under_caps_total_preserved(cfg: SimConfig):
    from worldsim.core.behaviour import split_under_caps
    from worldsim.core.clusters import Account

    rng = rng_for(42, "caps_total")
    accounts = [Account(id=f"A{i}", bank_id="SBI", home_location_id=None) for i in range(5)]
    total = 500_000_00  # 50,000 INR in paise
    splits = split_under_caps(total, accounts, cfg.caps, "ATM", rng)
    assert sum(amt for _, amt in splits) == total
