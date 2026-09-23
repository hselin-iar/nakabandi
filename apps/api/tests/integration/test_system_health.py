"""A5 Done When: "A public HTTPS URL serves the placeholder page and /api/v1/system/health."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from nakabandi.main import create_app


def test_health_returns_ok(client: TestClient) -> None:
    r = client.get("/api/v1/system/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_static_dir_is_not_mounted_when_unset(client: TestClient) -> None:
    # No STATIC_DIR set by the `client` fixture: the SPA mount is skipped, so an arbitrary root
    # path is a plain 404, not an attempt to serve a directory that does not exist.
    r = client.get("/some-spa-route")
    assert r.status_code == 404


def test_static_dir_is_served_when_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_url: str
) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html>placeholder</html>")

    monkeypatch.setenv("API_SERVICE_KEY", "test-only-service-key")
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("STATIC_DIR", str(static_dir))

    app = create_app()
    with TestClient(app) as c:
        r = c.get("/")
        assert r.status_code == 200
        assert "placeholder" in r.text
        # /api/v1/* still resolves to the API, not the static mount (registration order).
        health = c.get("/api/v1/system/health")
        assert health.status_code == 200
