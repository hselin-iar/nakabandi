"""Answers alerting's questions about the complaint an alert is anchored to (DOC 3 M4). Alerting
may not read intake's tables (LC-10), so it asks through this facade-exported lookup."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from nakabandi.intake.infrastructure.models import (
    AccountModel,
    CashOutObservationModel,
    ComplaintModel,
    FundHopModel,
)
from nakabandi.shared import SimTime, to_sim_time


@dataclass(frozen=True, slots=True)
class AccountTrace:
    complaint_id: str
    complaint_ref: str
    account_ref: str
    bank_id: str
    traced_accounts: list[str]
    disputed_paise: int


@dataclass(frozen=True, slots=True)
class TracedAccount:
    bank_id: str
    account_ref: str


@dataclass(frozen=True, slots=True)
class ComplaintSummary:
    category: str
    amount_paise: int


@dataclass(frozen=True, slots=True)
class ObservationSummary:
    id: str
    location_id: str
    event_at: SimTime


class LienContextLookup:
    def __init__(self, session: Session) -> None:
        self._session = session

    def for_account(self, complaint_id: str, account_id: str) -> AccountTrace | None:
        """The trace of `account_id` within ONE complaint: None unless that complaint's money
        reached the account (as its layer-1 account and/or through hops)."""
        account = self._session.get(AccountModel, account_id)
        complaint = self._session.get(ComplaintModel, complaint_id)
        if account is None or complaint is None:
            return None
        hops = list(
            self._session.scalars(
                select(FundHopModel).where(FundHopModel.complaint_id == complaint.id)
            )
        )
        is_layer1 = complaint.layer1_account_id == account_id
        if not is_layer1 and not any(h.to_account_id == account_id for h in hops):
            return None
        traced = {complaint.layer1_account_id}
        for hop in hops:
            traced.add(hop.from_account_id)
            traced.add(hop.to_account_id)
        disputed = sum(h.amount_paise for h in hops if h.to_account_id == account_id)
        if is_layer1:
            disputed += complaint.amount_paise
        return AccountTrace(
            complaint_id=complaint.id,
            complaint_ref=complaint.external_ref,
            account_ref=account.account_ref,
            bank_id=account.bank_id,
            traced_accounts=sorted(traced),
            disputed_paise=disputed,
        )

    def observation_summaries(self, observation_ids: list[str]) -> list[ObservationSummary]:
        """Where and when the given cash-outs happened, for ReconcileOutcome."""
        rows = self._session.scalars(
            select(CashOutObservationModel).where(CashOutObservationModel.id.in_(observation_ids))
        )
        return [
            ObservationSummary(id=o.id, location_id=o.location_id, event_at=to_sim_time(o.event_at))
            for o in rows
        ]

    def complaint_summary(self, complaint_id: str) -> ComplaintSummary | None:
        """Category and amount, for the analytics read model's rollup keys."""
        complaint = self._session.get(ComplaintModel, complaint_id)
        if complaint is None:
            return None
        return ComplaintSummary(category=complaint.category, amount_paise=complaint.amount_paise)

    def complaint_ref(self, complaint_id: str) -> str | None:
        complaint = self._session.get(ComplaintModel, complaint_id)
        return complaint.external_ref if complaint is not None else None

    def traced_accounts(self, complaint_id: str) -> list[TracedAccount]:
        """Every account the complaint's money reached, for the bank-facing informational notice."""
        complaint = self._session.get(ComplaintModel, complaint_id)
        if complaint is None:
            return []
        ids = {complaint.layer1_account_id}
        for hop in self._session.scalars(
            select(FundHopModel).where(FundHopModel.complaint_id == complaint_id)
        ):
            ids.add(hop.to_account_id)
        accounts = self._session.scalars(select(AccountModel).where(AccountModel.id.in_(ids)))
        return sorted(
            (TracedAccount(bank_id=a.bank_id, account_ref=a.account_ref) for a in accounts),
            key=lambda t: (t.bank_id, t.account_ref),
        )
