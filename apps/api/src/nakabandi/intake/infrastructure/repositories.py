"""SQLAlchemy repositories for intake (DOC 3 LC-9: obtain the session from the UnitOfWork,
never commit()). `as_of`-gated reads return only rows with `observed_at <= as_of` (LC-2)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from nakabandi.intake.domain.entities import (
    Account,
    CashOutObservation,
    Complaint,
    FundHop,
    IngestBatchRecord,
)
from nakabandi.intake.infrastructure.models import (
    AccountModel,
    CashOutObservationModel,
    ComplaintModel,
    FundHopModel,
    IngestBatchModel,
)
from nakabandi.shared import Id, SimTime, new_id


def _account_from_model(m: AccountModel) -> Account:
    return Account(
        id=m.id,
        account_ref=m.account_ref,
        bank_id=m.bank_id,
        home_location_id=m.home_location_id,
        home_district_id=m.home_district_id,
        first_seen_observed_at=m.first_seen_observed_at,
    )


def _complaint_from_model(m: ComplaintModel) -> Complaint:
    return Complaint(
        id=m.id,
        external_ref=m.external_ref,
        category=m.category,
        amount_paise=m.amount_paise,
        victim_district_id=m.victim_district_id,
        credited_at=m.credited_at,
        reported_event_at=m.reported_event_at,
        observed_at=m.observed_at,
        layer1_account_id=m.layer1_account_id,
        processing_status=m.processing_status,
        failed_stage=m.failed_stage,
    )


def _batch_from_model(m: IngestBatchModel) -> IngestBatchRecord:
    return IngestBatchRecord(
        id=m.id,
        idempotency_key=m.idempotency_key,
        source=m.source,
        received_at=m.received_at,
        row_counts=m.row_counts,
        response=m.response,
    )


class SqlAccountRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_or_create(
        self, *, account_ref: str, bank_id: Id, home_location_id: Id | None, observed_at: SimTime
    ) -> Account:
        existing = self._session.scalar(
            select(AccountModel).where(AccountModel.account_ref == account_ref)
        )
        if existing is not None:
            return _account_from_model(existing)

        model = AccountModel(
            id=new_id(),
            account_ref=account_ref,
            bank_id=bank_id,
            home_location_id=home_location_id,
            home_district_id=None,
            first_seen_observed_at=observed_at,
        )
        self._session.add(model)
        self._session.flush()
        return _account_from_model(model)

    def get_by_ref(self, account_ref: str) -> Account | None:
        model = self._session.scalar(
            select(AccountModel).where(AccountModel.account_ref == account_ref)
        )
        return _account_from_model(model) if model is not None else None


class SqlComplaintRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, complaint: Complaint) -> None:
        self._session.add(
            ComplaintModel(
                id=complaint.id,
                external_ref=complaint.external_ref,
                category=complaint.category,
                amount_paise=complaint.amount_paise,
                victim_district_id=complaint.victim_district_id,
                credited_at=complaint.credited_at,
                reported_event_at=complaint.reported_event_at,
                observed_at=complaint.observed_at,
                layer1_account_id=complaint.layer1_account_id,
                processing_status=complaint.processing_status,
                failed_stage=complaint.failed_stage,
            )
        )
        self._session.flush()

    def get_by_id(self, complaint_id: Id) -> Complaint | None:
        model = self._session.scalar(
            select(ComplaintModel).where(ComplaintModel.id == complaint_id)
        )
        return _complaint_from_model(model) if model is not None else None

    def mark_processed(self, complaint_id: Id) -> None:
        """Mark complaint as processed (pipeline completed all stages)."""
        model = self._session.scalar(
            select(ComplaintModel).where(ComplaintModel.id == complaint_id)
        )
        if model is not None:
            model.processing_status = "processed"
            model.failed_stage = None
            self._session.flush()

    def mark_unprocessed(self, complaint_id: Id, *, failed_stage: str) -> None:
        """Mark complaint as unprocessed with the name of the stage that failed."""
        model = self._session.scalar(
            select(ComplaintModel).where(ComplaintModel.id == complaint_id)
        )
        if model is not None:
            model.processing_status = "unprocessed"
            model.failed_stage = failed_stage
            self._session.flush()

    def list_unprocessed(self) -> list[Complaint]:
        """Return all complaints not yet successfully processed; used by RetryUnprocessed."""
        models = self._session.scalars(
            select(ComplaintModel).where(ComplaintModel.processing_status == "unprocessed")
        )
        return [_complaint_from_model(m) for m in models]

    def get_by_external_ref(self, external_ref: str) -> Complaint | None:
        model = self._session.scalar(
            select(ComplaintModel).where(ComplaintModel.external_ref == external_ref)
        )
        return _complaint_from_model(model) if model is not None else None

    def list_visible(self, as_of: SimTime) -> list[Complaint]:
        models = self._session.scalars(
            select(ComplaintModel).where(ComplaintModel.observed_at <= as_of)
        )
        return [_complaint_from_model(m) for m in models]


class SqlHopRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, hop: FundHop) -> None:
        self._session.add(
            FundHopModel(
                id=hop.id,
                complaint_id=hop.complaint_id,
                from_account_id=hop.from_account_id,
                to_account_id=hop.to_account_id,
                amount_paise=hop.amount_paise,
                layer=hop.layer,
                event_at=hop.event_at,
                observed_at=hop.observed_at,
            )
        )
        self._session.flush()


class SqlObservationRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, observation: CashOutObservation) -> None:
        self._session.add(
            CashOutObservationModel(
                id=observation.id,
                account_id=observation.account_id,
                location_id=observation.location_id,
                channel=observation.channel,
                amount_paise=observation.amount_paise,
                event_at=observation.event_at,
                observed_at=observation.observed_at,
                source=observation.source,
            )
        )
        self._session.flush()


class SqlBatchRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_idempotency_key(self, key: str) -> IngestBatchRecord | None:
        model = self._session.scalar(
            select(IngestBatchModel).where(IngestBatchModel.idempotency_key == key)
        )
        return _batch_from_model(model) if model is not None else None

    def record(self, batch: IngestBatchRecord) -> None:
        self._session.add(
            IngestBatchModel(
                id=batch.id,
                idempotency_key=batch.idempotency_key,
                source=batch.source,
                received_at=batch.received_at,
                row_counts=batch.row_counts,
                response=batch.response,
            )
        )
        self._session.flush()
