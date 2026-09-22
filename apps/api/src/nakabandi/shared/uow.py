"""UnitOfWork protocol (DOC 3 Shared Kernel, LC-9).

The SQLAlchemy implementation lives in shared/infrastructure/uow.py, added when a module first
needs storage (Step A3). Repositories obtain the active session from the UnitOfWork; they never
call commit() themselves.
"""

from __future__ import annotations

from typing import Protocol


class UnitOfWork(Protocol):
    def __enter__(self) -> UnitOfWork: ...

    def __exit__(self, exc_type, exc_value, traceback) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
