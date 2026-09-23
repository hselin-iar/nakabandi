"""ApplyCashOuts and ApplyConfirmedCashOut (DOC 3 M2 / S3): keep a cluster's location affinity
(cluster_location_stats) current as cash-outs are observed, so the next forecast for that cluster
sees them.

Two callers, one write path: a bank/simulator observation (ObservationIngested) and an officer's
confirmed cash-out location (S3 MarkOutcome). The stats are the ONLY thing graph derives from
observations; graph never reads intake's tables (the caller hands the facts in)."""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from nakabandi.graph.application.ports import ClusterRepo
from nakabandi.shared import ClusterUpdated, EventBus, Id, SimTime, new_id

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CashOutFact:
    """One cash-out, resolved by the caller to the graph's terms."""

    account_id: Id
    location_id: Id
    cell_id: Id
    district_id: Id
    amount_paise: int
    observed_at: SimTime


class ApplyCashOuts:
    def __init__(self, repo: ClusterRepo, bus: EventBus) -> None:
        self._repo = repo
        self._bus = bus

    def run(self, facts: list[CashOutFact], as_of: SimTime) -> int:
        """Add each cash-out to its account's cluster. An account not in any cluster yet is
        skipped (no cluster to attribute it to); returns how many were applied."""
        clusters = self._repo.get_cluster_ids_for_accounts([f.account_id for f in facts])
        touched: dict[Id, None] = {}
        applied = 0
        for fact in facts:
            cluster_id = clusters.get(fact.account_id)
            if cluster_id is None:
                continue
            self._repo.record_location_observation(
                cluster_id,
                fact.location_id,
                fact.cell_id,
                fact.district_id,
                fact.amount_paise,
                fact.observed_at,
            )
            touched[cluster_id] = None
            applied += 1
        for cluster_id in touched:
            self._bus.publish(
                ClusterUpdated(event_id=new_id(), occurred_at=as_of, cluster_id=cluster_id)
            )
        logger.info("graph.apply_cashouts", applied=applied, skipped=len(facts) - applied)
        return applied


class ApplyConfirmedCashOut:
    """An officer-confirmed cash-out (source "police_report"): an observation at `at`, always now,
    never earlier than data already held (DOC 3 S3 edge case). It carries no amount."""

    def __init__(self, repo: ClusterRepo, bus: EventBus) -> None:
        self._repo = repo
        self._bus = bus

    def run(
        self, cluster_id: Id, location_id: Id, cell_id: Id, district_id: Id, at: SimTime
    ) -> None:
        self._repo.record_location_observation(cluster_id, location_id, cell_id, district_id, 0, at)
        self._bus.publish(ClusterUpdated(event_id=new_id(), occurred_at=at, cluster_id=cluster_id))
        logger.info("graph.apply_confirmed", cluster_id=cluster_id, location_id=location_id)
