"""repo.py — EvidencePackRepo port + SqlEvidencePackRepo (DOC 3 S2, LC-10)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import sqlalchemy as sa
from nakabandi.casework.evidence.models import EvidencePackModel
from nakabandi.shared import Id, SimTime, to_sim_time
from sqlalchemy.orm import Session


@dataclass(frozen=True, slots=True)
class EvidencePackMeta:
    id: Id
    alert_id: Id
    case_id: Id | None
    version: int
    created_at: SimTime
    created_by_role: str
    sha256: str
    size_bytes: int
    audit_head_hash: str
    storage_path: str


class EvidencePackRepo(ABC):
    @abstractmethod
    def get(self, pack_id: Id) -> EvidencePackMeta | None: ...

    @abstractmethod
    def latest_version(self, alert_id: Id) -> int:
        """0 if no pack exists yet for this alert; packs are immutable, so a rebuild increments."""

    @abstractmethod
    def save(self, meta: EvidencePackMeta) -> None: ...


def _to_domain(row: EvidencePackModel) -> EvidencePackMeta:
    return EvidencePackMeta(
        id=row.id,
        alert_id=row.alert_id,
        case_id=row.case_id,
        version=row.version,
        created_at=to_sim_time(row.created_at),
        created_by_role=row.created_by_role,
        sha256=row.sha256,
        size_bytes=row.size_bytes,
        audit_head_hash=row.audit_head_hash,
        storage_path=row.storage_path,
    )


class SqlEvidencePackRepo(EvidencePackRepo):
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, pack_id: Id) -> EvidencePackMeta | None:
        row = self._s.get(EvidencePackModel, pack_id)
        return _to_domain(row) if row is not None else None

    def latest_version(self, alert_id: Id) -> int:
        version = self._s.scalar(
            sa.select(sa.func.max(EvidencePackModel.version)).where(
                EvidencePackModel.alert_id == alert_id
            )
        )
        return version or 0

    def save(self, meta: EvidencePackMeta) -> None:
        self._s.add(
            EvidencePackModel(
                id=meta.id,
                alert_id=meta.alert_id,
                case_id=meta.case_id,
                version=meta.version,
                created_at=meta.created_at,
                created_by_role=meta.created_by_role,
                sha256=meta.sha256,
                size_bytes=meta.size_bytes,
                audit_head_hash=meta.audit_head_hash,
                storage_path=meta.storage_path,
            )
        )
