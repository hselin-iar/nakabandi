"""SqlAuditRepo (DOC 3 M5: "INSERT and SELECT only; no update or delete method" — this class
offers exactly `append`, `last` and `list_all`, deliberately no update/delete method to add)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from nakabandi.audit.domain.entities import AuditEntry
from nakabandi.audit.infrastructure.models import AuditEntryModel


def _from_model(m: AuditEntryModel) -> AuditEntry:
    return AuditEntry(
        seq=m.seq,
        at=m.at,
        actor_id=m.actor_id,
        actor_role=m.actor_role,
        action=m.action,
        entity_type=m.entity_type,
        entity_id=m.entity_id,
        reason=m.reason,
        payload=m.payload,
        prev_hash=m.prev_hash,
        hash=m.hash,
    )


class SqlAuditRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, entry: AuditEntry) -> None:
        self._session.add(
            AuditEntryModel(
                seq=entry.seq,
                at=entry.at,
                actor_id=entry.actor_id,
                actor_role=entry.actor_role,
                action=entry.action,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                reason=entry.reason,
                payload=entry.payload,
                prev_hash=entry.prev_hash,
                hash=entry.hash,
            )
        )
        self._session.flush()

    def last(self) -> AuditEntry | None:
        model = self._session.scalar(
            select(AuditEntryModel).order_by(AuditEntryModel.seq.desc()).limit(1)
        )
        return _from_model(model) if model is not None else None

    def list_all(self) -> list[AuditEntry]:
        models = self._session.scalars(select(AuditEntryModel).order_by(AuditEntryModel.seq))
        return [_from_model(m) for m in models]
