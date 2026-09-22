"""Public facade of the audit module: what other modules may import (DOC 3).

AuditLog is constructed on the caller's active SQLAlchemy session, so an append always
participates in the caller's own transaction (DOC 3 M5: "the append and the audited action
commit or roll back together"). Called from access, and later from alerting and casework.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from nakabandi.audit.application.use_cases import AppendAudit, ListAudit, VerifyChain
from nakabandi.audit.domain.chain import VerifyReport
from nakabandi.audit.domain.entities import AuditEntry
from nakabandi.audit.infrastructure.audit_repo import SqlAuditRepo
from nakabandi.shared import Clock, Id

__all__ = ["AuditLog", "AuditEntry", "VerifyReport"]


class AuditLog:
    def __init__(self, session: Session, clock: Clock) -> None:
        repo = SqlAuditRepo(session)
        self._append = AppendAudit(repo, clock)
        self._verify = VerifyChain(repo)
        self._list = ListAudit(repo)

    def append(
        self,
        *,
        actor_id: Id,
        actor_role: str,
        action: str,
        entity_type: str,
        entity_id: Id,
        payload: dict,
        reason: str | None = None,
    ) -> AuditEntry:
        return self._append.run(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            reason=reason,
            payload=payload,
        )

    def verify(self) -> VerifyReport:
        return self._verify.run()

    def list(self) -> list[AuditEntry]:
        return self._list.run()
