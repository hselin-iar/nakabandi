"""SQLAlchemy implementation of the UnitOfWork port (DOC 3 Shared Kernel, LC-9).

Repositories obtain the active session from `.session`; they never call commit() themselves
(LC-9). Only `nakabandi.main` constructs this class; every module's application layer depends
only on the `UnitOfWork` protocol in `nakabandi.shared.uow`.
"""

from __future__ import annotations

from types import TracebackType

from sqlalchemy.orm import Session, sessionmaker


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self.session: Session | None = None

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        self.session = self._session_factory()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        assert self.session is not None
        if exc_type is not None:
            self.session.rollback()
        self.session.close()
        self.session = None

    def commit(self) -> None:
        assert self.session is not None
        self.session.commit()

    def rollback(self) -> None:
        assert self.session is not None
        self.session.rollback()
