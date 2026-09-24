"""SQLite has one writer (DOC 2 §2.8 T7). Found by the A11 stress run: with Python's default
deferred BEGIN, two requests that both READ and then WRITE make the second fail at once with
"database is locked" (a stale WAL snapshot cannot be upgraded; no busy timeout applies). Every
transaction now starts BEGIN IMMEDIATE, so contention queues instead of failing."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from nakabandi.shared.infrastructure.db import create_sqlite_engine, make_session_factory
from sqlalchemy import text


def _run(db: Path, immediate: bool, threads: int = 12, each: int = 15) -> list[str]:
    engine = create_sqlite_engine(f"sqlite:///{db}", immediate=immediate)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY, n INTEGER)"))
        conn.execute(text("INSERT INTO t (n) VALUES (0)"))
    factory = make_session_factory(engine)
    errors: list[str] = []
    lock = threading.Lock()

    def worker() -> None:
        for _ in range(each):
            try:
                with factory() as session:
                    n = session.execute(
                        text("SELECT n FROM t WHERE id = 1")
                    ).scalar_one()  # READ ...
                    session.execute(
                        text("UPDATE t SET n = :n WHERE id = 1"), {"n": n + 1}
                    )  # ... WRITE
                    session.commit()
            except Exception as exc:  # noqa: BLE001
                with lock:
                    errors.append(type(exc).__name__ + ": " + str(exc)[:60])

    with ThreadPoolExecutor(max_workers=threads) as pool:
        for _ in range(threads):
            pool.submit(worker)
    engine.dispose()
    return errors


def test_concurrent_read_then_write_transactions_queue_and_none_fail(tmp_path: Path) -> None:
    errors = _run(tmp_path / "immediate.db", immediate=True)
    assert errors == []

    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'immediate.db'}")
    with engine.connect() as conn:
        # no lost updates either: every one of the 12 x 15 read-modify-writes counted
        assert conn.execute(text("SELECT n FROM t WHERE id = 1")).scalar_one() == 12 * 15


def test_the_deferred_default_really_does_fail_under_the_same_load(tmp_path: Path) -> None:
    """The control: without BEGIN IMMEDIATE the same workload fails with "database is locked".
    If SQLite ever stopped doing that this test would say the fix is no longer needed."""
    errors = _run(tmp_path / "deferred.db", immediate=False)
    assert any("locked" in e for e in errors)
