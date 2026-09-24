"""case_repo.py — SqlCaseRepo: SQLAlchemy implementation of CaseRepo (DOC 3 LC-10)."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from nakabandi.casework.application.ports import CaseRepo
from nakabandi.casework.domain.case import AccountRef, Case, LocationHit
from nakabandi.casework.infrastructure.models import CaseModel
from nakabandi.shared import Id, to_sim_time


def _to_domain(row: CaseModel) -> Case:
    return Case(
        id=row.id,
        cluster_ref=row.cluster_ref,
        complaint_count=row.complaint_count,
        victim_count=row.victim_count,
        total_paise=row.total_paise,
        first_seen=to_sim_time(row.first_seen),
        last_seen=to_sim_time(row.last_seen),
        accounts=[AccountRef(**a) for a in row.accounts_json],
        top_locations=[
            LocationHit(
                location_id=h["location_id"],
                count=h["count"],
                last_at=to_sim_time(datetime.fromisoformat(h["last_at"])),
            )
            for h in row.top_locations_json
        ],
        sub_communities=list(row.sub_communities_json),
        timeline=[],
        brief_md=row.brief_md,
        single_complaint=row.single_complaint,
        built_at=to_sim_time(row.built_at) if row.built_at is not None else None,
    )


class SqlCaseRepo(CaseRepo):
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, case_id: Id) -> Case | None:
        row = self._s.get(CaseModel, case_id)
        return _to_domain(row) if row is not None else None

    def get_by_cluster(self, cluster_id: Id) -> Case | None:
        row = self._s.scalars(
            sa.select(CaseModel).where(CaseModel.cluster_ref == cluster_id)
        ).first()
        return _to_domain(row) if row is not None else None

    def save(self, case: Case) -> None:
        existing = self._s.get(CaseModel, case.id)
        values = {
            "id": case.id,
            "cluster_ref": case.cluster_ref,
            "complaint_count": case.complaint_count,
            "victim_count": case.victim_count,
            "total_paise": case.total_paise,
            "first_seen": case.first_seen,
            "last_seen": case.last_seen,
            "accounts_json": [
                {
                    "account_id": a.account_id,
                    "account_ref": a.account_ref,
                    "bank_id": a.bank_id,
                    "complaint_count": a.complaint_count,
                }
                for a in case.accounts
            ],
            "top_locations_json": [
                {"location_id": h.location_id, "count": h.count, "last_at": h.last_at.isoformat()}
                for h in case.top_locations
            ],
            "sub_communities_json": case.sub_communities,
            "timeline_json": [],
            "brief_md": case.brief_md,
            "single_complaint": case.single_complaint,
            "built_at": case.built_at,
        }
        if existing is None:
            self._s.add(CaseModel(**values))
        else:
            for key, value in values.items():
                setattr(existing, key, value)

    def list(self, cursor: Id | None, limit: int) -> tuple[list[Case], Id | None]:
        stmt = sa.select(CaseModel).order_by(CaseModel.id).limit(limit + 1)
        if cursor is not None:
            stmt = stmt.where(CaseModel.id > cursor)
        rows = list(self._s.scalars(stmt))
        next_cursor = rows[limit].id if len(rows) > limit else None
        return [_to_domain(r) for r in rows[:limit]], next_cursor
