"""A3 Done When (DOC 4 Step A3): posting the fixture returns accepted counts; resending with
the same idempotency key is a no-op; a malformed item is returned in rejected[] with index and
code; a record with observed_at later than the clock is invisible to as_of reads.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from nakabandi.intake.infrastructure.models import ComplaintModel
from nakabandi.intake.infrastructure.repositories import SqlComplaintRepo
from nakabandi.shared import SqlAlchemyUnitOfWork
from nakabandi.shared.infrastructure.db import create_sqlite_engine, make_session_factory
from sqlalchemy import select

FIXTURE = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "mini_ingest.json").read_text()
)
SERVICE_KEY = "test-only-service-key"
HEADERS = {"X-Nakabandi-Service-Key": SERVICE_KEY}


def _post_all_fixture_batches(client: TestClient) -> dict[str, Any]:
    responses: dict[str, Any] = {}
    r = client.post("/api/v1/ingest/registry", json=FIXTURE["registry"], headers=HEADERS)
    assert r.status_code == 200, r.text
    responses["registry"] = r.json()

    r = client.post("/api/v1/ingest/complaints", json=FIXTURE["complaints"], headers=HEADERS)
    assert r.status_code == 200, r.text
    responses["complaints"] = r.json()

    r = client.post("/api/v1/ingest/hops", json=FIXTURE["hops"], headers=HEADERS)
    assert r.status_code == 200, r.text
    responses["hops"] = r.json()

    r = client.post(
        "/api/v1/ingest/cashout-observations",
        json=FIXTURE["cashout_observations"],
        headers=HEADERS,
    )
    assert r.status_code == 200, r.text
    responses["cashout_observations"] = r.json()

    for tick in FIXTURE["ticks"]:
        r = client.post("/api/v1/ingest/tick", json=tick, headers=HEADERS)
        assert r.status_code == 200, r.text
    return responses


def test_missing_service_key_is_rejected(client: TestClient) -> None:
    r = client.post("/api/v1/ingest/registry", json=FIXTURE["registry"])
    assert r.status_code == 401


def test_posting_the_fixture_returns_accepted_counts(client: TestClient) -> None:
    responses = _post_all_fixture_batches(client)

    # 2 banks + 2 regions + 1 cell + 2 locations + 1 unit
    assert responses["registry"]["accepted"] == 8
    assert responses["registry"]["rejected"] == []

    assert responses["complaints"]["accepted"] == 4
    assert responses["complaints"]["rejected"] == []

    assert responses["cashout_observations"]["accepted"] == 3
    assert responses["cashout_observations"]["rejected"] == []


def test_a_malformed_item_is_rejected_with_index_and_code(client: TestClient) -> None:
    client.post("/api/v1/ingest/registry", json=FIXTURE["registry"], headers=HEADERS)
    client.post("/api/v1/ingest/complaints", json=FIXTURE["complaints"], headers=HEADERS)

    r = client.post("/api/v1/ingest/hops", json=FIXTURE["hops"], headers=HEADERS)
    body = r.json()

    assert body["accepted"] == 2
    assert len(body["rejected"]) == 1
    assert body["rejected"][0]["index"] == 2  # the third hop, referencing an unknown complaint
    assert body["rejected"][0]["code"] == "HOP_UNKNOWN_COMPLAINT"


def test_resending_with_the_same_idempotency_key_is_a_no_op(client: TestClient) -> None:
    r1 = client.post("/api/v1/ingest/complaints", json=FIXTURE["complaints"], headers=HEADERS)
    r2 = client.post("/api/v1/ingest/complaints", json=FIXTURE["complaints"], headers=HEADERS)
    assert r1.json() == r2.json()

    # Proof it was not reprocessed, not just coincidentally identical: a second batch reusing
    # the same idempotency_key but different content still replays the first response verbatim.
    changed = dict(FIXTURE["complaints"])
    changed["items"] = []
    r3 = client.post("/api/v1/ingest/complaints", json=changed, headers=HEADERS)
    assert r3.json() == r1.json()


def test_observed_at_later_than_clock_is_invisible_to_as_of_reads(
    client: TestClient, db_url: str
) -> None:
    r = client.post("/api/v1/ingest/complaints", json=FIXTURE["complaints"], headers=HEADERS)
    assert r.status_code == 200, r.text

    session_factory = make_session_factory(create_sqlite_engine(db_url))
    with SqlAlchemyUnitOfWork(session_factory) as uow:
        assert uow.session is not None
        one_complaint = uow.session.scalar(select(ComplaintModel).limit(1))
        assert one_complaint is not None
        as_of_before = one_complaint.observed_at.replace(year=one_complaint.observed_at.year - 1)
        repo = SqlComplaintRepo(uow.session)
        assert repo.list_visible(as_of=one_complaint.observed_at) != []
        assert repo.list_visible(as_of=as_of_before) == []
