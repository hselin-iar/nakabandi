"""Answers alerting.RecordAction's question "which complaint was this account traced from, and how
much of it is disputed here?" (DOC 3 M4 RecordAction step 3). Alerting may not read intake's
tables (LC-10), so it asks through this facade-exported lookup."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from nakabandi.intake.infrastructure.models import AccountModel, ComplaintModel, FundHopModel


@dataclass(frozen=True, slots=True)
class AccountTrace:
    complaint_id: str
    complaint_ref: str
    account_ref: str
    bank_id: str
    traced_accounts: list[str]
    disputed_paise: int


class LienContextLookup:
    def __init__(self, session: Session) -> None:
        self._session = session

    def for_account(self, account_id: str) -> AccountTrace | None:
        """The most recently observed complaint whose money reached this account: as its first
        layer account (the victim's own transfer, complaint.amount_paise) and/or through hops."""
        account = self._session.get(AccountModel, account_id)
        if account is None:
            return None
        complaint = self._session.scalars(
            select(ComplaintModel)
            .where(
                or_(
                    ComplaintModel.layer1_account_id == account_id,
                    ComplaintModel.id.in_(
                        select(FundHopModel.complaint_id).where(
                            FundHopModel.to_account_id == account_id
                        )
                    ),
                )
            )
            .order_by(ComplaintModel.observed_at.desc())
            .limit(1)
        ).first()
        if complaint is None:
            return None

        hops = list(
            self._session.scalars(
                select(FundHopModel).where(FundHopModel.complaint_id == complaint.id)
            )
        )
        traced = {complaint.layer1_account_id}
        for hop in hops:
            traced.add(hop.from_account_id)
            traced.add(hop.to_account_id)
        disputed = sum(h.amount_paise for h in hops if h.to_account_id == account_id)
        if complaint.layer1_account_id == account_id:
            disputed += complaint.amount_paise
        return AccountTrace(
            complaint_id=complaint.id,
            complaint_ref=complaint.external_ref,
            account_ref=account.account_ref,
            bank_id=account.bank_id,
            traced_accounts=sorted(traced),
            disputed_paise=disputed,
        )
