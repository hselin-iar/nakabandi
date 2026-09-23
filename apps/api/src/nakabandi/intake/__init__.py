"""Public facade of the intake module: what other modules may import (DOC 3).

IngestService bundles the five ingest use cases on one SQLAlchemy session, so `nakabandi.main`'s
routers and `scripts/seed` call the exact same code path (DOC 3 A3 "What to build": "npm run
seed CLI that loads a JSONL file through the SAME use cases (no bypass)").
"""

from __future__ import annotations

from nakabandi_contracts.ingest import (
    CashOutObservationBatch,
    ComplaintBatch,
    HopBatch,
    IngestResponse,
    RegistryUpdate,
    Tick,
)
from sqlalchemy.orm import Session

from nakabandi.geo import GeoService
from nakabandi.intake.application.use_cases import (
    AdvanceClock,
    IngestComplaints,
    IngestHooks,
    IngestHops,
    IngestObservations,
    IngestRegistry,
)
from nakabandi.intake.infrastructure.lien_lookup import (
    AccountTrace,
    ComplaintDetail,
    ComplaintSummary,
    LienContextLookup,
    ObservationSummary,
    TracedAccount,
)
from nakabandi.intake.infrastructure.repositories import (
    SqlAccountRepo,
    SqlBatchRepo,
    SqlComplaintRepo,
    SqlHopRepo,
    SqlObservationRepo,
)
from nakabandi.shared import EventBus, SimClock, SimTime

__all__ = [
    "IngestService",
    "latest_ingest_sim_time",
    "IngestHooks",
    "LienContextLookup",
    "AccountTrace",
    "ComplaintSummary",
    "ComplaintDetail",
    "ObservationSummary",
    "TracedAccount",
]


def latest_ingest_sim_time(session: Session) -> SimTime | None:
    """The sim time of the newest ingest batch, or None on an empty database. main.py restores
    the (in-memory) SimClock from it at boot, so a restart resumes where the world stopped."""
    return SqlBatchRepo(session).latest_received_at()


class IngestService:
    def __init__(
        self,
        session: Session,
        clock: SimClock,
        bus: EventBus | None = None,
        hooks: IngestHooks | None = None,
    ) -> None:
        complaint_repo = SqlComplaintRepo(session)
        account_repo = SqlAccountRepo(session)
        batch_repo = SqlBatchRepo(session)

        self._complaints = IngestComplaints(complaint_repo, account_repo, batch_repo, clock, hooks)
        self._hops = IngestHops(
            SqlHopRepo(session), account_repo, complaint_repo, batch_repo, clock, hooks
        )
        self._observations = IngestObservations(
            SqlObservationRepo(session), account_repo, batch_repo, clock, bus
        )
        self._registry = IngestRegistry(GeoService(session), batch_repo, clock, hooks)
        self._tick = AdvanceClock(clock)

    def ingest_registry(self, update: RegistryUpdate) -> IngestResponse:
        return self._registry.run(update)

    def ingest_complaints(self, batch: ComplaintBatch) -> IngestResponse:
        return self._complaints.run(batch)

    def ingest_hops(self, batch: HopBatch) -> IngestResponse:
        return self._hops.run(batch)

    def ingest_observations(self, batch: CashOutObservationBatch) -> IngestResponse:
        return self._observations.run(batch)

    def advance_clock(self, tick: Tick) -> IngestResponse:
        return self._tick.run(tick)
