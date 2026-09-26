"""Answers alerting's questions about the complaint an alert is anchored to (DOC 3 M4). Alerting
may not read intake's tables (LC-10), so it asks through this facade-exported lookup."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import or_, select
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
    account_id: str
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
    account_id: str = ""
    amount_paise: int = 0
    observed_at: SimTime | None = None


@dataclass(frozen=True, slots=True)
class AccountInfo:
    account_id: str
    account_ref: str
    bank_id: str


@dataclass(frozen=True, slots=True)
class ComplaintFact:
    """One complaint whose money reached a set of accounts (casework's build_case, DOC 3 S1)."""

    id: str
    external_ref: str
    victim_district_id: str
    amount_paise: int
    reported_event_at: SimTime
    touched_account_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ComplaintDetail:
    """A complaint with the facts the forecast chain needs about it and its first-layer account."""

    id: str
    external_ref: str
    category: str
    amount_paise: int
    credited_at: SimTime
    reported_event_at: SimTime
    victim_district_id: str
    layer1_account_id: str
    layer1_bank_id: str
    layer1_home_location_id: str | None
    layer1_home_district_id: str | None


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
            ObservationSummary(
                id=o.id,
                location_id=o.location_id,
                event_at=to_sim_time(o.event_at),
                account_id=o.account_id,
                amount_paise=o.amount_paise,
                observed_at=to_sim_time(o.observed_at),
            )
            for o in rows
        ]

    # ---- the forecast chain (pipeline adapters) -------------------------------------------

    def complaint_detail(self, complaint_id: str) -> ComplaintDetail | None:
        complaint = self._session.get(ComplaintModel, complaint_id)
        if complaint is None:
            return None
        account = self._session.get(AccountModel, complaint.layer1_account_id)
        assert account is not None  # a complaint's layer-1 account is a foreign key
        return ComplaintDetail(
            id=complaint.id,
            external_ref=complaint.external_ref,
            category=complaint.category,
            amount_paise=complaint.amount_paise,
            credited_at=to_sim_time(complaint.credited_at),
            reported_event_at=to_sim_time(complaint.reported_event_at),
            victim_district_id=complaint.victim_district_id,
            layer1_account_id=account.id,
            layer1_bank_id=account.bank_id,
            layer1_home_location_id=account.home_location_id,
            layer1_home_district_id=account.home_district_id,
        )

    def complaints_up_to(self, as_of: SimTime) -> list[ComplaintDetail]:
        """Every complaint observed by `as_of` (LC-2), for forecast/TrainModels (DOC 3 M2 B6):
        building historical training examples needs to enumerate complaints, not just look one
        up by id."""
        details: list[ComplaintDetail] = []
        for complaint in self._session.scalars(
            select(ComplaintModel).where(ComplaintModel.observed_at <= as_of)
        ):
            detail = self.complaint_detail(complaint.id)
            if detail is not None:
                details.append(detail)
        return sorted(details, key=lambda d: d.reported_event_at)

    def first_cashout_after(
        self, account_ids: list[str], after: SimTime, as_of: SimTime
    ) -> tuple[str, SimTime] | None:
        """(location_id, event_at) of the earliest cash-out at any of these accounts with
        event_at >= `after`, from what was known by `as_of` (observed_at <= as_of, LC-2). Used
        by TrainModels to label a complaint's candidate list with its real outcome — mirrors
        `cluster_delays_min`'s as-of bound but returns the location instead of just the delay."""
        if not account_ids:
            return None
        best: tuple[str, SimTime] | None = None
        for obs in self._session.scalars(
            select(CashOutObservationModel).where(
                CashOutObservationModel.account_id.in_(account_ids),
                CashOutObservationModel.observed_at <= as_of,
            )
        ):
            event_at = to_sim_time(obs.event_at)
            if event_at < after:
                continue
            if best is None or event_at < best[1]:
                best = (obs.location_id, event_at)
        return best

    def accounts_of(self, complaint_id: str) -> list[str]:
        """Every account a complaint's money reached (layer 1 and each hop's ends), sorted."""
        complaint = self._session.get(ComplaintModel, complaint_id)
        if complaint is None:
            return []
        ids = {complaint.layer1_account_id}
        for hop in self._session.scalars(
            select(FundHopModel).where(FundHopModel.complaint_id == complaint_id)
        ):
            ids.add(hop.from_account_id)
            ids.add(hop.to_account_id)
        return sorted(ids)

    def disputed_by_account(self, complaint_id: str) -> dict[str, int]:
        """Paise this complaint traced INTO each account: hops into it, plus the victim's own
        transfer into the layer-1 account (DOC 3 M6 build_lien "disputed")."""
        complaint = self._session.get(ComplaintModel, complaint_id)
        if complaint is None:
            return {}
        out: dict[str, int] = {complaint.layer1_account_id: complaint.amount_paise}
        for hop in self._session.scalars(
            select(FundHopModel).where(FundHopModel.complaint_id == complaint_id)
        ):
            out[hop.to_account_id] = out.get(hop.to_account_id, 0) + hop.amount_paise
        return out

    def accounts_by_ids(self, account_ids: list[str]) -> list[AccountInfo]:
        """Account ref and bank for a set of account ids (casework's build_case, DOC 3 S1)."""
        if not account_ids:
            return []
        rows = self._session.scalars(select(AccountModel).where(AccountModel.id.in_(account_ids)))
        infos = (
            AccountInfo(account_id=a.id, account_ref=a.account_ref, bank_id=a.bank_id) for a in rows
        )
        return sorted(infos, key=lambda i: i.account_id)

    def complaints_for_accounts(self, account_ids: list[str]) -> list[ComplaintFact]:
        """Every complaint whose money reached any of these accounts, as a layer-1 account or a
        hop's end (casework's build_case, DOC 3 S1)."""
        if not account_ids:
            return []
        matching_ids = set(
            self._session.scalars(
                select(ComplaintModel.id).where(
                    or_(
                        ComplaintModel.layer1_account_id.in_(account_ids),
                        ComplaintModel.id.in_(
                            select(FundHopModel.complaint_id).where(
                                or_(
                                    FundHopModel.to_account_id.in_(account_ids),
                                    FundHopModel.from_account_id.in_(account_ids),
                                )
                            )
                        ),
                    )
                )
            )
        )
        if not matching_ids:
            return []
        facts: list[ComplaintFact] = []
        for complaint in self._session.scalars(
            select(ComplaintModel).where(ComplaintModel.id.in_(matching_ids))
        ):
            touched = {complaint.layer1_account_id}
            for hop in self._session.scalars(
                select(FundHopModel).where(FundHopModel.complaint_id == complaint.id)
            ):
                touched.add(hop.from_account_id)
                touched.add(hop.to_account_id)
            facts.append(
                ComplaintFact(
                    id=complaint.id,
                    external_ref=complaint.external_ref,
                    victim_district_id=complaint.victim_district_id,
                    amount_paise=complaint.amount_paise,
                    reported_event_at=to_sim_time(complaint.reported_event_at),
                    touched_account_ids=tuple(sorted(touched)),
                )
            )
        return sorted(facts, key=lambda f: f.id)

    def hops_among(self, account_ids: list[str]) -> list[tuple[str, str, int, int, SimTime]]:
        """(from_account_id, to_account_id, amount_paise, layer, event_at) for every hop with
        both ends inside this set of accounts (casework's cluster graph, DOC 3 S1; layer/event_at
        feed the fund-flow directed timeline, Frontend Strategy §7.4)."""
        if not account_ids:
            return []
        rows = self._session.execute(
            select(
                FundHopModel.from_account_id,
                FundHopModel.to_account_id,
                FundHopModel.amount_paise,
                FundHopModel.layer,
                FundHopModel.event_at,
            ).where(
                FundHopModel.from_account_id.in_(account_ids),
                FundHopModel.to_account_id.in_(account_ids),
            )
        ).all()
        return [
            (r.from_account_id, r.to_account_id, r.amount_paise, r.layer, to_sim_time(r.event_at))
            for r in rows
        ]

    def all_cashout_events(self) -> list[tuple[str, SimTime]]:
        """Every cash-out ever observed, as (location_id, observed_at), across every cluster —
        the raw feed for forecast's global (cross-cluster) as-of density feature
        (`global_cashout_rate`, DOC 3 M2). As-of bounding happens downstream in the pure
        GlobalCashoutIndex, not here (LC-2 still holds: callers must never look past their own
        as_of when they call snapshot_at)."""
        rows = self._session.execute(
            select(CashOutObservationModel.location_id, CashOutObservationModel.observed_at)
        ).all()
        return [(r.location_id, to_sim_time(r.observed_at)) for r in rows]

    def cluster_delays_min(self, account_ids: list[str], as_of: SimTime) -> list[float]:
        """Observed credit-to-cash-out delays (minutes) at these accounts, from what was known by
        `as_of` (observed_at <= as_of, LC-2): each cash-out is timed from the earliest complaint
        credit, at or before it, that traced money into that account."""
        if not account_ids:
            return []
        traced_credit: dict[str, list[SimTime]] = {}
        for account_id in account_ids:
            credits = [
                to_sim_time(c)
                for c in self._session.scalars(
                    select(ComplaintModel.credited_at).where(
                        or_(
                            ComplaintModel.layer1_account_id == account_id,
                            ComplaintModel.id.in_(
                                select(FundHopModel.complaint_id).where(
                                    FundHopModel.to_account_id == account_id
                                )
                            ),
                        )
                    )
                )
            ]
            traced_credit[account_id] = credits
        delays: list[float] = []
        for obs in self._session.scalars(
            select(CashOutObservationModel).where(
                CashOutObservationModel.account_id.in_(account_ids),
                CashOutObservationModel.observed_at <= as_of,
            )
        ):
            event_at = to_sim_time(obs.event_at)
            earlier = [c for c in traced_credit.get(obs.account_id, []) if c <= event_at]
            if earlier:
                delays.append((event_at - min(earlier)).total_seconds() / 60.0)
        return sorted(delays)

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
            (
                TracedAccount(account_id=a.id, bank_id=a.bank_id, account_ref=a.account_ref)
                for a in accounts
            ),
            key=lambda t: (t.bank_id, t.account_ref),
        )
