"""ports.py — Repository abstraction for casework's own `cases` table (DOC 3 LC-10), and the two
small read ports BundleCluster needs from graph and intake (adapters built in casework/__init__.py,
mirroring alerting's AlertDetailSource pattern so application/ never imports another module
directly)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from nakabandi.casework.domain.case import AccountFact, Case, ClusterSnapshot, ComplaintFact
from nakabandi.shared import Id, SimTime


class ClusterSource(Protocol):
    def snapshot(self, cluster_id: Id, as_of: SimTime) -> ClusterSnapshot: ...
    def account_ids(self, cluster_id: Id) -> list[Id]: ...


class ComplaintSource(Protocol):
    def complaints_for_accounts(self, account_ids: list[Id]) -> list[ComplaintFact]: ...
    def accounts_by_ids(self, account_ids: list[Id]) -> list[AccountFact]: ...
    def hops_among(self, account_ids: list[Id]) -> list[tuple[Id, Id, int]]: ...


class CaseRepo(ABC):
    @abstractmethod
    def get(self, case_id: Id) -> Case | None: ...

    @abstractmethod
    def get_by_cluster(self, cluster_id: Id) -> Case | None: ...

    @abstractmethod
    def save(self, case: Case) -> None:
        """Upsert by id (a rebuild replaces the previous row for the same cluster)."""

    @abstractmethod
    def list(self, cursor: Id | None, limit: int) -> tuple[list[Case], Id | None]:
        """Ordered by id (ULIDs sort by creation time); returns (page, next_cursor)."""
