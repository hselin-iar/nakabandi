"""Regression: an injected cluster must own real accounts, so its hops form a network.

It used to be created with accounts=[]; every complaint routed to it then got an innocent
stand-in layer-1 account and every hop pointed back at that same account (spiral graphs, one
single-node cluster per complaint downstream).
"""

from __future__ import annotations

from worldsim.cli import _build_world
from worldsim.core.config import SimConfig
from worldsim.core.generator import CashOutTruth, ComplaintTruth, HopTruth
from worldsim.core.scenarios import inject_cluster


def _world():
    return _build_world(SimConfig.from_yaml("config/sim.default.yaml"))


def test_injected_cluster_gets_size_accounts() -> None:
    world = _world()
    district = world.registry.districts[0].id
    cid = inject_cluster(world, district, 15, 0.8, "district", sim_now=1.0)
    cluster = next(c for c in world.clusters if c.id == cid)
    assert len(cluster.accounts) == 15
    assert len({a.id for a in cluster.accounts}) == 15


def test_injected_cluster_hops_are_not_self_loops_on_innocent_accounts() -> None:
    world = _world()
    cid = inject_cluster(world, world.registry.districts[0].id, 15, 0.8, "district", sim_now=1.0)
    events = []
    t = 1.0
    while t < 3.0:
        events += world.step(t, t + 0.1)
        t += 0.1
    complaints = [e for e in events if isinstance(e, ComplaintTruth) and e.cluster_id == cid]
    hops = [e for e in events if isinstance(e, HopTruth) and e.cluster_id == cid]
    assert complaints and hops
    assert not any(c.account_id.startswith("INNO-") for c in complaints)
    assert len({h.to_account_id for h in hops}) > 1
    assert sum(h.from_account_id == h.to_account_id for h in hops) < len(hops) // 5
    assert any(isinstance(e, CashOutTruth) for e in events)


def test_cluster_without_accounts_receives_no_complaints() -> None:
    world = _world()
    for c in world.clusters:
        c.accounts.clear()
    events = world.step(1.0, 2.0)
    assert not any(isinstance(e, HopTruth) for e in events)
