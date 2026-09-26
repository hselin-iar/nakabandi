"""Shared fixtures for integration tests: a fresh app + fresh SQLite file per test, so tests
never share state (or a rate limiter, DOC 4 Step A4) with each other."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from nakabandi.main import create_app

SERVICE_KEY = "test-only-service-key"
HEADERS = {"X-Nakabandi-Service-Key": SERVICE_KEY}


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture
def client(db_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("API_SERVICE_KEY", SERVICE_KEY)
    monkeypatch.setenv("DATABASE_URL", db_url)
    # Isolated, guaranteed-empty model store: without this, tests pick up whatever real model
    # scripts/train.py last wrote to the repo's models/ dir, trained on a completely different
    # (and much larger) registry — its predictions don't clear these tests' tiny fixtures'
    # confidence floor, so alerts silently stop raising. Tests must see the same fallback
    # heuristic scorer they were written against, not whatever happens to be on disk.
    monkeypatch.setenv("NAKABANDI_MODEL_STORE_DIR", str(tmp_path / "models"))
    app = create_app()
    with TestClient(app) as c:
        yield c
