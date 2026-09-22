"""AppendAudit, VerifyChain, ListAudit (DOC 3 M5 FUNCTION & CLASS DESIGN).

AppendAudit computes `seq` as last seq + 1 and `hash` from the chain, inside the caller's own
UnitOfWork: it never commits (LC-9), so the audit row and the action it records share one
transaction and commit or roll back together (DOC 3 M5).
"""

from __future__ import annotations

from dataclasses import replace

from nakabandi.audit.application.ports import AuditRepo
from nakabandi.audit.domain.chain import (
    GENESIS_HASH,
    VerifyReport,
    compute_hash,
    entry_content,
    verify_chain,
)
from nakabandi.audit.domain.entities import AuditEntry
from nakabandi.shared import Clock, Id


class AppendAudit:
    def __init__(self, audit_repo: AuditRepo, clock: Clock) -> None:
        self._repo = audit_repo
        self._clock = clock

    def run(
        self,
        *,
        actor_id: Id,
        actor_role: str,
        action: str,
        entity_type: str,
        entity_id: Id,
        reason: str | None,
        payload: dict,
    ) -> AuditEntry:
        last = self._repo.last()
        seq = (last.seq + 1) if last is not None else 1
        prev_hash = last.hash if last is not None else GENESIS_HASH

        provisional = AuditEntry(
            seq=seq,
            at=self._clock.now(),
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            reason=reason,
            payload=payload,
            prev_hash=prev_hash,
            hash="",
        )
        entry = replace(provisional, hash=compute_hash(prev_hash, entry_content(provisional)))
        self._repo.append(entry)
        return entry


class VerifyChain:
    def __init__(self, audit_repo: AuditRepo) -> None:
        self._repo = audit_repo

    def run(self) -> VerifyReport:
        return verify_chain(self._repo.list_all())


class ListAudit:
    def __init__(self, audit_repo: AuditRepo) -> None:
        self._repo = audit_repo

    def run(self) -> list[AuditEntry]:
        return self._repo.list_all()
