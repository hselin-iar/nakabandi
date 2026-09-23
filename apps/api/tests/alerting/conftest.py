"""The alerting integration tests' shared `client`: the real app on a fresh database, with the mini
registry, its complaints and hops already ingested through the ingest API (no bypass)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from nakabandi.main import create_app

SERVICE_KEY = "test-only-service-key"
WEBHOOK_SECRET = "test-webhook-secret"
_FIXTURE = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "mini_ingest.json").read_text()
)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("API_SERVICE_KEY", SERVICE_KEY)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'alerting.db'}")
    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-at-least-32-bytes-long")
    monkeypatch.setenv("WEBHOOK_SECRET", WEBHOOK_SECRET)
    with TestClient(create_app()) as c:
        for key in ("registry", "complaints", "hops"):
            r = c.post(
                f"/api/v1/ingest/{key}",
                json=_FIXTURE[key],
                headers={"X-Nakabandi-Service-Key": SERVICE_KEY},
            )
            assert r.status_code == 200, r.text
        yield c
