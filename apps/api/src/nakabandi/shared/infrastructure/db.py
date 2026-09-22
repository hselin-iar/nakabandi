"""SQLite/WAL engine, declarative Base and session factory (DOC 2 §2.3: "SQLite 3 in WAL
mode via SQLAlchemy 2.0, behind repository ports").

`Base` is one shared declarative base so every module's ORM models (each module owns only its
own tables, LC-10) live in one MetaData and `create_all` builds the whole schema in one call.
Only `nakabandi.main` (composition root) and each module's own infrastructure layer touch this
file; other modules reach `Base` through the shared facade (`nakabandi.shared.Base`).
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def create_sqlite_engine(url: str) -> Engine:
    """WAL mode and foreign keys are session-level PRAGMAs in SQLite: they must be set on every
    new connection, not once on the engine (DOC 2 §2.3)."""
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def create_all(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
