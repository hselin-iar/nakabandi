"""SQLite/WAL engine, declarative Base and session factory (DOC 2 §2.3: "SQLite 3 in WAL
mode via SQLAlchemy 2.0, behind repository ports").

`Base` is one shared declarative base so every module's ORM models (each module owns only its
own tables, LC-10) live in one MetaData and `create_all` builds the whole schema in one call.
Only `nakabandi.main` (composition root) and each module's own infrastructure layer touch this
file; other modules reach `Base` and `UTCDateTime` through the shared facade.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator


class Base(DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator):
    """A tz-aware UTC datetime column that actually round-trips as tz-aware (LC-2: SimTime is
    always tz-aware UTC). SQLite's driver silently returns a NAIVE datetime from a plain
    `DateTime(timezone=True)` column on read, even though the value stored was tz-aware; every
    module's timestamp columns use this instead so a value read back always has tzinfo, not
    just the one written. Found via the audit hash chain (a re-read row's recomputed hash
    stopped matching its stored hash, purely because of the missing tzinfo on read — no
    tampering involved), but the underlying gap affects every DateTime column, not just audit's.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("a naive datetime was given to a UTCDateTime column (LC-2)")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


BUSY_TIMEOUT_MS = 30_000


def create_sqlite_engine(url: str, *, immediate: bool = True) -> Engine:
    """WAL mode and foreign keys are session-level PRAGMAs in SQLite: they must be set on every
    new connection, not once on the engine (DOC 2 §2.3).

    Concurrency (DOC 2 §2.8 T7, found by the A11 stress run): SQLite has ONE writer. With Python's
    default deferred BEGIN, two requests that both read and then write make the second fail at
    once with "database is locked" (a stale WAL snapshot cannot be upgraded, and no busy timeout
    helps). So every transaction begins with BEGIN IMMEDIATE, which takes the write lock up front
    and WAITS for it (busy_timeout), turning contention into queueing instead of errors. A
    read-only engine (`immediate=False`) keeps deferred transactions: readers never block on the
    writer under WAL."""
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection: object, _connection_record: object) -> None:
        dbapi_connection.isolation_level = None  # type: ignore[attr-defined]  # we emit BEGIN
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")  # safe under WAL; far fewer fsyncs
        cursor.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        cursor.close()

    @event.listens_for(engine, "begin")
    def _begin(conn: object) -> None:
        conn.exec_driver_sql("BEGIN IMMEDIATE" if immediate else "BEGIN")  # type: ignore[attr-defined]

    return engine


def create_all(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
