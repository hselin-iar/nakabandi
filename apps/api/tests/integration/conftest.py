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
def client(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("API_SERVICE_KEY", SERVICE_KEY)
    monkeypatch.setenv("DATABASE_URL", db_url)
    app = create_app()
    with TestClient(app) as c:
        yield c
