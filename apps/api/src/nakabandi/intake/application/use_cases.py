"""Intake use cases (DOC 3 M2): IngestComplaints, IngestHops, IngestObservations,
IngestRegistry, AdvanceClock.

Idempotency: each batch endpoint replays the stored IngestResponse verbatim when the same
`idempotency_key` is seen again (A3 Done When: "resending ... is a no-op"), never reprocesses.
A per-item failure is reported in `rejected[]` and never stops the rest of the batch (DOC 3 M2
ERROR HANDLING STRATEGY). Every batch also advances the SimClock to `batch.sim_time` (A3 "What
to build": "SimClock advances from batch sim_time and Tick").

DomainEvent publishing for LC-3 (ComplaintIngested, HopsIngested, ObservationIngested,
TickAdvanced) is deferred to Step A6 (Pipeline v0 & Golden Test), the first consumer.
"""

from __future__ import annotations

import structlog
from nakabandi_contracts.ingest import (
    CashOutObservationBatch,
    ComplaintBatch,
    HopBatch,
    IngestResponse,
    RegistryUpdate,
    RejectedItem,
    Tick,
)

from nakabandi.geo import GeoService
from nakabandi.intake.application.ports import (
    AccountRepo,
    BatchRepo,
    ComplaintRepo,
    HopRepo,
    ObservationRepo,
)
from nakabandi.intake.domain.entities import (
    CashOutObservation,
    Complaint,
    FundHop,
    IngestBatchRecord,
)
from nakabandi.intake.domain.validation import normalise_ref, validate_complaint
from nakabandi.shared import (
    DomainError,
    EventBus,
    ObservationIngested,
    SimClock,
    SimTime,
    ValidationFailed,
    new_id,
)


def _replay_if_seen(batch_repo: BatchRepo, idempotency_key: str) -> IngestResponse | None:
    existing = batch_repo.get_by_idempotency_key(idempotency_key)
    if existing is not None and existing.response is not None:
        return IngestResponse.model_validate(existing.response)
    return None


logger = structlog.get_logger(__name__)


def _record_batch(
    batch_repo: BatchRepo,
    *,
    idempotency_key: str,
    source: str,
    received_at: SimTime,
    response: IngestResponse,
) -> None:
    batch_repo.record(
        IngestBatchRecord(
            id=new_id(),
            idempotency_key=idempotency_key,
            source=source,
            received_at=received_at,
            row_counts={"accepted": response.accepted, "rejected": len(response.rejected)},
            response=response.model_dump(mode="json"),
        )
    )


class IngestComplaints:
    def __init__(
        self,
        complaint_repo: ComplaintRepo,
        account_repo: AccountRepo,
        batch_repo: BatchRepo,
        clock: SimClock,
    ) -> None:
        self._complaints = complaint_repo
        self._accounts = account_repo
        self._batches = batch_repo
        self._clock = clock

    def run(self, batch: ComplaintBatch) -> IngestResponse:
        replayed = _replay_if_seen(self._batches, batch.idempotency_key)
        if replayed is not None:
            return replayed

        accepted = 0
        rejected: list[RejectedItem] = []
        for index, item in enumerate(batch.items):
            try:
                validate_complaint(item)
                if self._complaints.get_by_external_ref(item.external_ref) is not None:
                    accepted += 1  # DOC 3 M2 edge case: duplicate external_ref is idempotent
                    continue
                account = self._accounts.get_or_create(
                    account_ref=normalise_ref(item.layer1_account.account_ref),
                    bank_id=item.layer1_account.bank_id,
                    home_location_id=item.layer1_account.home_location_id,
                    observed_at=item.observed_at,
                )
                self._complaints.add(
                    Complaint(
                        id=new_id(),
                        external_ref=item.external_ref,
                        category=item.category.value,
                        amount_paise=item.amount_paise,
                        victim_district_id=item.victim_district_id,
                        credited_at=item.credited_at,
                        reported_event_at=item.reported_event_at,
                        observed_at=item.observed_at,
                        layer1_account_id=account.id,
                    )
                )
                accepted += 1
            except DomainError as exc:
                rejected.append(RejectedItem(index=index, code=exc.code, message=exc.message))

        self._clock.advance_to(batch.sim_time)
        response = IngestResponse(accepted=accepted, rejected=rejected, sim_time=self._clock.now())
        _record_batch(
            self._batches,
            idempotency_key=batch.idempotency_key,
            source="complaints",
            received_at=self._clock.now(),
            response=response,
        )
        return response


class IngestHops:
    def __init__(
        self,
        hop_repo: HopRepo,
        account_repo: AccountRepo,
        complaint_repo: ComplaintRepo,
        batch_repo: BatchRepo,
        clock: SimClock,
    ) -> None:
        self._hops = hop_repo
        self._accounts = account_repo
        self._complaints = complaint_repo
        self._batches = batch_repo
        self._clock = clock

    def run(self, batch: HopBatch) -> IngestResponse:
        replayed = _replay_if_seen(self._batches, batch.idempotency_key)
        if replayed is not None:
            return replayed

        accepted = 0
        rejected: list[RejectedItem] = []
        for index, item in enumerate(batch.items):
            try:
                complaint = self._complaints.get_by_external_ref(item.complaint_external_ref)
                if complaint is None:
                    raise ValidationFailed(
                        "HOP_UNKNOWN_COMPLAINT",
                        f"no complaint known for external_ref {item.complaint_external_ref!r}",
                    )
                from_account = self._accounts.get_or_create(
                    account_ref=normalise_ref(item.from_account.account_ref),
                    bank_id=item.from_account.bank_id,
                    home_location_id=item.from_account.home_location_id,
                    observed_at=item.observed_at,
                )
                to_account = self._accounts.get_or_create(
                    account_ref=normalise_ref(item.to_account.account_ref),
                    bank_id=item.to_account.bank_id,
                    home_location_id=item.to_account.home_location_id,
                    observed_at=item.observed_at,
                )
                self._hops.add(
                    FundHop(
                        id=new_id(),
                        complaint_id=complaint.id,
                        from_account_id=from_account.id,
                        to_account_id=to_account.id,
                        amount_paise=item.amount_paise,
                        layer=item.layer,
                        event_at=item.event_at,
                        observed_at=item.observed_at,
                    )
                )
                accepted += 1
            except DomainError as exc:
                rejected.append(RejectedItem(index=index, code=exc.code, message=exc.message))

        self._clock.advance_to(batch.sim_time)
        response = IngestResponse(accepted=accepted, rejected=rejected, sim_time=self._clock.now())
        _record_batch(
            self._batches,
            idempotency_key=batch.idempotency_key,
            source="hops",
            received_at=self._clock.now(),
            response=response,
        )
        return response


class IngestObservations:
    def __init__(
        self,
        observation_repo: ObservationRepo,
        account_repo: AccountRepo,
        batch_repo: BatchRepo,
        clock: SimClock,
        bus: EventBus | None = None,
    ) -> None:
        self._observations = observation_repo
        self._accounts = account_repo
        self._batches = batch_repo
        self._clock = clock
        self._bus = bus

    def run(self, batch: CashOutObservationBatch) -> IngestResponse:
        replayed = _replay_if_seen(self._batches, batch.idempotency_key)
        if replayed is not None:
            return replayed

        accepted = 0
        accepted_ids: list[str] = []
        rejected: list[RejectedItem] = []
        for index, item in enumerate(batch.items):
            try:
                account = self._accounts.get_by_ref(normalise_ref(item.account_ref))
                if account is None:
                    raise ValidationFailed(
                        "ACCOUNT_UNKNOWN", f"no account known for ref {item.account_ref!r}"
                    )
                observation_id = new_id()
                self._observations.add(
                    CashOutObservation(
                        id=observation_id,
                        account_id=account.id,
                        location_id=item.location_id,
                        channel=item.channel.value,
                        amount_paise=item.amount_paise,
                        event_at=item.event_at,
                        observed_at=item.observed_at,
                        source=item.source,
                    )
                )
                accepted += 1
                accepted_ids.append(observation_id)
            except DomainError as exc:
                rejected.append(RejectedItem(index=index, code=exc.code, message=exc.message))

        self._clock.advance_to(batch.sim_time)
        response = IngestResponse(accepted=accepted, rejected=rejected, sim_time=self._clock.now())
        _record_batch(
            self._batches,
            idempotency_key=batch.idempotency_key,
            source="cashout_observations",
            received_at=self._clock.now(),
            response=response,
        )
        self._announce(accepted_ids)
        return response

    def _announce(self, observation_ids: list[str]) -> None:
        """LC-3 ObservationIngested, once per batch, after its rows are added: ReconcileOutcome
        listens. A failing subscriber is logged and must not reject an accepted batch."""
        if self._bus is None or not observation_ids:
            return
        try:
            self._bus.publish(
                ObservationIngested(
                    event_id=new_id(),
                    occurred_at=self._clock.now(),
                    observation_ids=observation_ids,
                )
            )
        except Exception:
            logger.exception("intake.observation_ingested.publish_failed")


class IngestRegistry:
    def __init__(self, geo: GeoService, batch_repo: BatchRepo, clock: SimClock) -> None:
        self._geo = geo
        self._batches = batch_repo
        self._clock = clock

    def run(self, update: RegistryUpdate) -> IngestResponse:
        idempotency_key = f"registry:{update.version}"
        replayed = _replay_if_seen(self._batches, idempotency_key)
        if replayed is not None:
            return replayed

        result = self._geo.apply_registry(
            banks=update.banks,
            regions=update.regions,
            cells=update.cells,
            locations=update.locations,
            units=update.units,
        )
        rejected = [
            RejectedItem(index=row.index, code=row.code, message=row.message)
            for row in result.rejected
        ]
        response = IngestResponse(
            accepted=result.accepted, rejected=rejected, sim_time=self._clock.now()
        )
        _record_batch(
            self._batches,
            idempotency_key=idempotency_key,
            source="registry",
            received_at=self._clock.now(),
            response=response,
        )
        return response


class AdvanceClock:
    def __init__(self, clock: SimClock) -> None:
        self._clock = clock

    def run(self, tick: Tick) -> IngestResponse:
        self._clock.advance_to(tick.sim_time)
        return IngestResponse(accepted=1, rejected=[], sim_time=self._clock.now())
