"""bundle.py — build_case (DOC 3 S1 FUNCTION & CLASS DESIGN). Pure: no I/O, no database, no
wall clock. The application layer (BundleCluster) gathers cluster_view/complaints/accounts through
other modules' facades and hands them here already assembled.

Honest simplification (see docs/state/track-a.md Learnings [A12]): the schema has no victim/
complainant identity separate from a complaint (ComplaintModel carries no victim_id), so
victim_count is one victim per complaint — the same count as complaint_count — rather than a
distinct-victim tally the data cannot support.
"""

from __future__ import annotations

from nakabandi.casework.domain.case import (
    AccountFact,
    AccountRef,
    Case,
    ClusterSnapshot,
    ComplaintFact,
    LocationHit,
)
from nakabandi.shared import Id, SimTime, new_id


def build_case(
    cluster_view: ClusterSnapshot,
    complaints: list[ComplaintFact],
    accounts: list[AccountFact],
    as_of: SimTime,
    existing_id: Id | None = None,
) -> Case:
    account_complaint_counts: dict[Id, int] = {a.account_id: 0 for a in accounts}
    for complaint in complaints:
        for account_id in complaint.touched_account_ids:
            if account_id in account_complaint_counts:
                account_complaint_counts[account_id] += 1

    account_refs = [
        AccountRef(
            account_id=a.account_id,
            account_ref=a.account_ref,
            bank_id=a.bank_id,
            complaint_count=account_complaint_counts.get(a.account_id, 0),
        )
        for a in accounts
    ]

    reported_ats = [c.reported_event_at for c in complaints]
    first_seen = min(reported_ats) if reported_ats else as_of
    last_seen = cluster_view.last_seen_at or (max(reported_ats) if reported_ats else as_of)

    top_locations = [
        LocationHit(location_id=loc_id, count=count, last_at=last_seen)
        for loc_id, count in cluster_view.top_locations
    ]

    return Case(
        id=existing_id or new_id(),
        cluster_ref=cluster_view.cluster_id,
        complaint_count=len(complaints),
        victim_count=len(complaints),
        total_paise=sum(c.amount_paise for c in complaints),
        first_seen=first_seen,
        last_seen=last_seen,
        accounts=account_refs,
        top_locations=top_locations,
        sub_communities=[list(g) for g in cluster_view.sub_communities],
        timeline=[],
        single_complaint=len(complaints) <= 1,
        built_at=as_of,
    )
