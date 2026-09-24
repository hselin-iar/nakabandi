"""Public facade of the casework module: what other modules may import (DOC 3 S1, S2).

Exports:
  CaseService        — bundle(cluster_id), get(case_id), list(cursor, limit),
                        build_evidence_pack(principal, alert_id), get_evidence_pack(pack_id),
                        download_evidence_pack(pack_id), register_subscribers(bus)
  Case, AccountRef, LocationHit  — value objects (read-only by callers)
  EvidencePackMeta               — evidence pack metadata (read-only by callers)
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import structlog
from sqlalchemy.orm import Session

from nakabandi.access import Permission, Principal, Role
from nakabandi.audit import AuditLog
from nakabandi.casework.application.ports import ClusterSource, ComplaintSource
from nakabandi.casework.application.use_cases import BundleCluster, GetCase, ListCases
from nakabandi.casework.domain.case import (
    AccountRef,
    Case,
    ClusterEdge,
    ClusterGraph,
    ClusterNode,
    LocationHit,
)
from nakabandi.casework.evidence.file_store import FileStore
from nakabandi.casework.evidence.repo import EvidencePackMeta, SqlEvidencePackRepo
from nakabandi.casework.evidence.service import AlertSource, BuildEvidencePack
from nakabandi.casework.infrastructure.case_repo import SqlCaseRepo
from nakabandi.shared import Clock, ClusterUpdated, EventBus, Id, NotFound

logger = structlog.get_logger(__name__)

__all__ = [
    "CaseService",
    "Case",
    "AccountRef",
    "LocationHit",
    "EvidencePackMeta",
    "ClusterGraph",
    "ClusterNode",
    "ClusterEdge",
]

MAX_GRAPH_NODES = 200


class CaseService:
    """Façade: the ONLY casework object other modules may import.

    Constructed per request/unit-of-work on the caller's own session, like AccessService and
    AuditLog, so a case rebuild and the event that triggered it share one transaction.
    """

    def __init__(
        self,
        session: Session,
        clock: Clock,
        cluster_source: ClusterSource,
        complaint_source: ComplaintSource,
        alert_source: AlertSource,
        role_permissions: Mapping[Role, frozenset[Permission]],
        file_store: FileStore,
        debounce_min: float,
        font_path: Path | None = None,
    ) -> None:
        self._repo = SqlCaseRepo(session)
        self._pack_repo = SqlEvidencePackRepo(session)
        self._file_store = file_store
        self._bundle_uc = BundleCluster(
            self._repo, cluster_source, complaint_source, clock, debounce_min
        )
        self._get_uc = GetCase(self._repo)
        self._list_uc = ListCases(self._repo)
        self._cluster_source = cluster_source
        self._complaint_source = complaint_source
        self._build_pack_uc = BuildEvidencePack(
            alert_source=alert_source,
            case_repo=self._repo,
            audit=AuditLog(session, clock),
            pack_repo=self._pack_repo,
            file_store=file_store,
            role_permissions=role_permissions,
            clock=clock,
            font_path=font_path,
        )

    # ------------------------------------------------------------------
    # S1: cases and clusters
    # ------------------------------------------------------------------

    def bundle(self, cluster_id: Id, force: bool = False) -> Case:
        return self._bundle_uc.run(cluster_id, force=force)

    def get(self, case_id: Id) -> Case:
        return self._get_uc.run(case_id)

    def list(self, cursor: Id | None, limit: int) -> tuple[list[Case], Id | None]:
        return self._list_uc.run(cursor, limit)

    def cluster_graph(self, cluster_id: Id) -> ClusterGraph:
        """DOC 3 S1 GET /clusters/{id}. Unmasked: the interfaces layer applies access.mask_ref
        per node for the calling principal before this leaves the process."""
        account_ids = self._cluster_source.account_ids(cluster_id)
        accounts = self._complaint_source.accounts_by_ids(account_ids)
        capped = accounts[:MAX_GRAPH_NODES]
        capped_ids = {a.account_id for a in capped}
        nodes = [
            ClusterNode(
                id=a.account_id, kind="account", account_ref=a.account_ref, bank_id=a.bank_id
            )
            for a in capped
        ]
        edges = [
            ClusterEdge(from_id=f, to_id=t, amount_paise=amt)
            for f, t, amt in self._complaint_source.hops_among(account_ids)
            if f in capped_ids and t in capped_ids
        ]
        return ClusterGraph(
            cluster_ref=cluster_id,
            size=len(account_ids),
            status="active",
            novelty=0.0,
            nodes=nodes,
            edges=edges,
        )

    def register_subscribers(self, bus: EventBus) -> None:
        """Rebuild a cluster's case on ClusterUpdated, debounced (DOC 3 S1). A rebuild failure
        keeps the previous version and logs (DOC 3 S1 error-handling strategy); it never fails
        the publisher's own transaction."""

        def on_cluster_updated(event: ClusterUpdated) -> None:
            try:
                self.bundle(event.cluster_id)
            except Exception:
                logger.exception("casework.bundle.failed", cluster_id=event.cluster_id)

        bus.subscribe(ClusterUpdated, on_cluster_updated)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # S2: evidence packs
    # ------------------------------------------------------------------

    def build_evidence_pack(self, principal: Principal, alert_id: Id) -> EvidencePackMeta:
        return self._build_pack_uc.run(principal, alert_id)

    def get_evidence_pack(self, pack_id: Id) -> EvidencePackMeta:
        meta = self._pack_repo.get(pack_id)
        if meta is None:
            raise NotFound("EVIDENCE_PACK_NOT_FOUND", f"Evidence pack {pack_id!r} not found")
        return meta

    def download_evidence_pack(self, pack_id: Id) -> bytes:
        meta = self.get_evidence_pack(pack_id)
        return self._file_store.read(meta.storage_path)
