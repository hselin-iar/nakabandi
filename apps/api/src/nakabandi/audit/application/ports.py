"""Repository port for audit (DOC 3 M5: audit_repo.py "INSERT and SELECT only; no update or
delete method"). This Protocol mirrors that on purpose: it has no update or delete method to
implement in the first place."""

from __future__ import annotations

from typing import Protocol

from nakabandi.audit.domain.entities import AuditEntry


class AuditRepo(Protocol):
    def append(self, entry: AuditEntry) -> None: ...
    def last(self) -> AuditEntry | None: ...
    def list_all(self) -> list[AuditEntry]:
        """Ascending seq order."""
        ...
