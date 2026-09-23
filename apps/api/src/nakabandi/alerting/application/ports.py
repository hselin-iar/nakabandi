"""Alerting application ports (Protocols) (DOC 3 M4 application/ports.py)."""

from __future__ import annotations

from typing import Any, Protocol

from nakabandi.shared import Id


class AlertRepo(Protocol):
    """Read/write access to the alerts table (LC-10 alerting owns alerts)."""

    def get_by_id(self, alert_id: Id) -> Any | None: ...

    def get_by_dedup_key(self, dedup_key: str) -> Any | None:
        """Return the open alert with this dedup_key, or None."""
        ...

    def list_open(self) -> list[Any]: ...

    def list_by_scope(
        self,
        *,
        state_id: str | None = None,
        district_id: str | None = None,
        bank_id: str | None = None,
        status: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Any], str | None]:
        """Paginated listing filtered by principal scope. Returns (items, next_cursor)."""
        ...

    def save(self, alert: Any) -> None: ...


class OutcomeRepo(Protocol):
    """Read/write access to the outcomes table."""

    def save(self, outcome: Any) -> None: ...


class DirectoryPort(Protocol):
    """Stub port for the geo directory (real implementation lands at Sync 4)."""

    def get_recipients(self, alert: Any) -> list[Any]: ...
