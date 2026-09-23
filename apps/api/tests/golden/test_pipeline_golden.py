"""A6 golden test (DOC 4 Step A6 Done When).

Verifies that the pipeline, using stub facades, processes the mini_ingest fixture
end-to-end and that:
  1. All complaints are marked `processed` after ProcessComplaint runs.
  2. An alert_id is produced for every non-stale complaint.
  3. A forced stage failure leaves the complaint `unprocessed` with the correct
     failed_stage set, and RetryUnprocessed recovers it.

This test harness uses a real SQLite DB (same as integration tests) and the existing
ingest API to load the fixture — no bypass of use cases (DOC 3 A3 note).

STUB/MOCK STRATEGY (DOC 4 A6): real facades replace stubs one at a time at Sync 3.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from nakabandi.intake.infrastructure.models import ComplaintModel
from nakabandi.intake.infrastructure.repositories import SqlComplaintRepo
from nakabandi.main import create_app
from nakabandi.pipeline import ProcessComplaint, RetryUnprocessed
from nakabandi.shared.infrastructure.db import create_sqlite_engine, make_session_factory
from sqlalchemy import select
from stubs.pipeline_stubs import (
    StubAlertService,
    StubClusterService,
    StubForecaster,
    StubInterceptor,
)

# ---------------------------------------------------------------------------
# Fixture data
# ---------------------------------------------------------------------------

FIXTURE = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "mini_ingest.json").read_text()
)
SERVICE_KEY = "test-only-service-key"
HEADERS = {"X-Nakabandi-Service-Key": SERVICE_KEY}

SIM_NOW = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pipeline(session: Any, alert_svc: StubAlertService) -> ProcessComplaint:
    """Wire ProcessComplaint with all stub facades."""
    complaint_repo = SqlComplaintRepo(session)
    cluster_svc = StubClusterService()
    forecaster = StubForecaster()
    interceptor = StubInterceptor()
    return ProcessComplaint(
        complaint_repo=complaint_repo,
        cluster_service=cluster_svc,
        forecaster=forecaster,
        interceptor=interceptor,
        alert_service=alert_svc,
    )


def _load_fixture_via_api(client: TestClient) -> None:
    """Post all mini_ingest fixture batches through the real ingest API."""
    r = client.post("/api/v1/ingest/registry", json=FIXTURE["registry"], headers=HEADERS)
    assert r.status_code == 200, r.text

    r = client.post("/api/v1/ingest/complaints", json=FIXTURE["complaints"], headers=HEADERS)
    assert r.status_code == 200, r.text

    r = client.post("/api/v1/ingest/hops", json=FIXTURE["hops"], headers=HEADERS)
    assert r.status_code == 200, r.text

    r = client.post(
        "/api/v1/ingest/cashout-observations",
        json=FIXTURE["cashout_observations"],
        headers=HEADERS,
    )
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGoldenScenario:
    """Golden scenario: pipeline processes the mini_ingest fixture end-to-end."""

    def test_all_complaints_processed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All complaints in the fixture are marked `processed` and produce an alert."""
        db_url = f"sqlite:///{tmp_path / 'golden.db'}"
        monkeypatch.setenv("API_SERVICE_KEY", SERVICE_KEY)
        monkeypatch.setenv("DATABASE_URL", db_url)

        app = create_app()

        with TestClient(app) as client:
            _load_fixture_via_api(client)

            # Wire the pipeline directly against the same DB (no bypass of schema/tables)
            engine = create_sqlite_engine(db_url)
            Session = make_session_factory(engine)
            alert_svc = StubAlertService()

            with Session() as session:
                pipeline = _make_pipeline(session, alert_svc)

                # Run ProcessComplaint for every complaint in the DB
                all_complaints = session.scalars(select(ComplaintModel)).all()
                assert len(all_complaints) > 0, "No complaints loaded from fixture"

                results = [pipeline.run(c.id, SIM_NOW) for c in all_complaints]
                session.commit()

            # All complaints should now be marked processed
            with Session() as session:
                remaining = session.scalars(
                    select(ComplaintModel).where(ComplaintModel.processing_status == "unprocessed")
                ).all()
                assert remaining == [], (
                    f"Expected all complaints processed; still unprocessed: "
                    f"{[r.id for r in remaining]}"
                )

            # Each successful result must have an alert_id
            ok_results = [r for r in results if r.ok]
            assert len(ok_results) == len(all_complaints), (
                f"Some results failed: {[r for r in results if not r.ok]}"
            )
            for r in ok_results:
                assert r.alert_id is not None, f"Expected alert_id for complaint {r.complaint_id}"

            # The stub alert service recorded the same count
            assert len(alert_svc.raised) == len(all_complaints)

    def test_forced_stage_failure_leaves_unprocessed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A forced forecast failure leaves the complaint unprocessed with the stage name."""
        db_url = f"sqlite:///{tmp_path / 'failure.db'}"
        monkeypatch.setenv("API_SERVICE_KEY", SERVICE_KEY)
        monkeypatch.setenv("DATABASE_URL", db_url)

        app = create_app()

        with TestClient(app) as client:
            _load_fixture_via_api(client)

        engine = create_sqlite_engine(db_url)
        Session = make_session_factory(engine)

        # Patch the forecaster to raise
        class BrokenForecaster:
            def generate(self, ctx: Any, as_of: Any) -> Any:
                raise RuntimeError("deliberate forecast failure")

        with Session() as session:
            repo = SqlComplaintRepo(session)
            alert_svc = StubAlertService()
            pipeline = ProcessComplaint(
                complaint_repo=repo,
                cluster_service=StubClusterService(),
                forecaster=BrokenForecaster(),
                interceptor=StubInterceptor(),
                alert_service=alert_svc,
            )

            all_complaints = session.scalars(select(ComplaintModel)).all()
            assert len(all_complaints) > 0

            # Process the first complaint only
            first = all_complaints[0]
            result = pipeline.run(first.id, SIM_NOW)
            session.commit()

        assert not result.ok, "Expected failure result"
        assert result.failed_stage == "forecast.generate", (
            f"Expected 'forecast.generate', got {result.failed_stage!r}"
        )

        # Verify in DB
        with Session() as session:
            model = session.scalar(select(ComplaintModel).where(ComplaintModel.id == first.id))
            assert model is not None
            assert model.processing_status == "unprocessed"
            assert model.failed_stage == "forecast.generate"

        # No alerts raised (failure before alerting stage)
        assert alert_svc.raised == []

    def test_retry_unprocessed_recovers_complaint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RetryUnprocessed recovers a complaint that was left unprocessed."""
        db_url = f"sqlite:///{tmp_path / 'retry.db'}"
        monkeypatch.setenv("API_SERVICE_KEY", SERVICE_KEY)
        monkeypatch.setenv("DATABASE_URL", db_url)

        app = create_app()

        with TestClient(app) as client:
            _load_fixture_via_api(client)

        engine = create_sqlite_engine(db_url)
        Session = make_session_factory(engine)

        # Step 1: force a failure on all complaints
        class BrokenAlertService:
            def raise_or_merge(self, *args: Any, **kwargs: Any) -> Any:
                raise RuntimeError("deliberate alerting failure")

        with Session() as session:
            repo = SqlComplaintRepo(session)
            pipeline = ProcessComplaint(
                complaint_repo=repo,
                cluster_service=StubClusterService(),
                forecaster=StubForecaster(),
                interceptor=StubInterceptor(),
                alert_service=BrokenAlertService(),
            )
            all_complaints = session.scalars(select(ComplaintModel)).all()
            for c in all_complaints:
                pipeline.run(c.id, SIM_NOW)
            session.commit()

        # Step 2: verify they are all unprocessed
        with Session() as session:
            unprocessed = session.scalars(
                select(ComplaintModel).where(ComplaintModel.processing_status == "unprocessed")
            ).all()
            n_unprocessed = len(unprocessed)
        assert n_unprocessed > 0

        # Step 3: RetryUnprocessed with a working alert service
        alert_svc = StubAlertService()
        with Session() as session:
            repo = SqlComplaintRepo(session)
            pipeline = ProcessComplaint(
                complaint_repo=repo,
                cluster_service=StubClusterService(),
                forecaster=StubForecaster(),
                interceptor=StubInterceptor(),
                alert_service=alert_svc,
            )
            retry = RetryUnprocessed(complaint_repo=repo, process_complaint=pipeline)
            results = retry.run(SIM_NOW)
            session.commit()

        assert all(r.ok for r in results), (
            f"Some retries still failed: {[r for r in results if not r.ok]}"
        )
        assert len(results) == n_unprocessed

        # Step 4: confirm all processed in DB
        with Session() as session:
            remaining = session.scalars(
                select(ComplaintModel).where(ComplaintModel.processing_status == "unprocessed")
            ).all()
            assert remaining == [], "Still unprocessed after retry"
