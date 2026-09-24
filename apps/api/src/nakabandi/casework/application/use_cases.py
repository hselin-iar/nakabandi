"""use_cases.py — BundleCluster, GetCase, ListCases (DOC 3 S1).

SRP (DOC 3 S1): build_case aggregates, render_brief formats, this use case fetches and stores.
"""

from __future__ import annotations

from dataclasses import replace

from nakabandi.casework.application.ports import CaseRepo, ClusterSource, ComplaintSource
from nakabandi.casework.domain.brief import render_brief
from nakabandi.casework.domain.bundle import build_case
from nakabandi.casework.domain.case import Case
from nakabandi.shared import Clock, Id, NotFound


class BundleCluster:
    """Rebuilds a cluster's case, debounced to at most once per `debounce_min` sim-minutes unless
    `force` is set (on-demand, DOC 3 S1 "BundleCluster.run(cluster_id): ... and on demand")."""

    def __init__(
        self,
        repo: CaseRepo,
        cluster_source: ClusterSource,
        complaint_source: ComplaintSource,
        clock: Clock,
        debounce_min: float,
    ) -> None:
        self._repo = repo
        self._cluster_source = cluster_source
        self._complaint_source = complaint_source
        self._clock = clock
        self._debounce_min = debounce_min

    def run(self, cluster_id: Id, force: bool = False) -> Case:
        as_of = self._clock.now()
        existing = self._repo.get_by_cluster(cluster_id)
        if not force and existing is not None and existing.built_at is not None:
            elapsed_min = (as_of - existing.built_at).total_seconds() / 60
            if elapsed_min < self._debounce_min:
                return existing

        account_ids = self._cluster_source.account_ids(cluster_id)
        accounts = self._complaint_source.accounts_by_ids(account_ids)
        complaints = self._complaint_source.complaints_for_accounts(account_ids)
        cluster_view = self._cluster_source.snapshot(cluster_id, as_of)

        case = build_case(
            cluster_view,
            complaints,
            accounts,
            as_of,
            existing_id=existing.id if existing is not None else None,
        )
        case = replace(case, brief_md=render_brief(case))
        self._repo.save(case)
        return case


class GetCase:
    def __init__(self, repo: CaseRepo) -> None:
        self._repo = repo

    def run(self, case_id: Id) -> Case:
        case = self._repo.get(case_id)
        if case is None:
            raise NotFound("CASE_NOT_FOUND", f"Case {case_id!r} not found")
        return case


class ListCases:
    def __init__(self, repo: CaseRepo) -> None:
        self._repo = repo

    def run(self, cursor: Id | None, limit: int) -> tuple[list[Case], Id | None]:
        return self._repo.list(cursor, limit)
