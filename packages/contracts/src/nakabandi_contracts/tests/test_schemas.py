"""LC-1: schema round-trip and example-payload validation (DOC 3 Shared Kernel, TESTING PLAN)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from nakabandi_contracts import ingest

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"

# Mirrors scripts/gen_contract_schemas.py's TOP_LEVEL_MODELS. Duplicated rather than imported
# so this test does not reach across the repo root into scripts/ (contracts stays a leaf).
TOP_LEVEL_MODELS = {
    "ComplaintBatch": ingest.ComplaintBatch,
    "HopBatch": ingest.HopBatch,
    "CashOutObservationBatch": ingest.CashOutObservationBatch,
    "RegistryUpdate": ingest.RegistryUpdate,
    "Tick": ingest.Tick,
    "IngestResponse": ingest.IngestResponse,
}

NOW = "2026-01-15T10:00:00+05:30"
LATER = "2026-01-15T10:05:00+05:30"

SAMPLE_ACCOUNT = {"account_ref": "acc-1", "bank_id": "bank-1"}

SAMPLE_PAYLOADS = {
    "ComplaintBatch": {
        "batch_id": "b1",
        "idempotency_key": "k1",
        "sim_time": NOW,
        "items": [
            {
                "external_ref": "c1",
                "category": "upi_phishing",
                "amount_paise": 500000,
                "victim_district_id": "d1",
                "credited_at": NOW,
                "reported_event_at": NOW,
                "observed_at": LATER,
                "layer1_account": SAMPLE_ACCOUNT,
            }
        ],
    },
    "HopBatch": {
        "batch_id": "b2",
        "idempotency_key": "k2",
        "sim_time": NOW,
        "items": [
            {
                "complaint_external_ref": "c1",
                "from_account": SAMPLE_ACCOUNT,
                "to_account": {"account_ref": "acc-2", "bank_id": "bank-2"},
                "amount_paise": 400000,
                "layer": 1,
                "event_at": NOW,
                "observed_at": LATER,
            }
        ],
    },
    "CashOutObservationBatch": {
        "batch_id": "b3",
        "idempotency_key": "k3",
        "sim_time": NOW,
        "items": [
            {
                "account_ref": "acc-2",
                "location_id": "loc-1",
                "channel": "ATM",
                "amount_paise": 300000,
                "event_at": NOW,
                "observed_at": LATER,
                "source": "bank_report",
            }
        ],
    },
    "RegistryUpdate": {
        "version": "v1",
        "banks": [],
        "regions": [],
        "cells": [],
        "locations": [
            {
                "id": "loc-1",
                "kind": "ATM",
                "bank_id": "bank-1",
                "lat": 12.9,
                "lon": 77.6,
                "district_id": "d1",
                "cell_id": "cell-1",
                "source": "osm",
                "display_name": "MG Road ATM",
                "area_type": "urban",
                "activity_index": 0.5,
            }
        ],
        "units": [
            {
                "id": "unit-1",
                "kind": "station",
                "district_id": "d1",
                "lat": 12.9,
                "lon": 77.6,
                "status": "active",
            }
        ],
    },
    "Tick": {"sim_time": NOW},
    "IngestResponse": {"accepted": 1, "rejected": [], "sim_time": NOW},
}


@pytest.mark.parametrize("name", sorted(TOP_LEVEL_MODELS))
def test_schema_has_no_diff_from_model(name: str) -> None:
    """Guards `npm run types`: the committed .json must match model_json_schema()."""
    committed = json.loads((SCHEMA_DIR / f"{name}.json").read_text())
    current = TOP_LEVEL_MODELS[name].model_json_schema()
    assert committed == current, f"{name}.json is stale; run scripts/gen_contract_schemas.py"


@pytest.mark.parametrize("name", sorted(SAMPLE_PAYLOADS))
def test_sample_payload_validates_against_model(name: str) -> None:
    model = TOP_LEVEL_MODELS[name]
    model.model_validate(SAMPLE_PAYLOADS[name])


@pytest.mark.parametrize("name", sorted(SAMPLE_PAYLOADS))
def test_sample_payload_validates_against_committed_schema(name: str) -> None:
    schema = json.loads((SCHEMA_DIR / f"{name}.json").read_text())
    jsonschema.validate(SAMPLE_PAYLOADS[name], schema)


def test_naive_datetime_is_rejected() -> None:
    bad = dict(SAMPLE_PAYLOADS["Tick"])
    bad["sim_time"] = "2026-01-15T10:00:00"  # no offset: naive
    with pytest.raises(ValidationError):
        ingest.Tick.model_validate(bad)


def test_unknown_enum_value_is_rejected_not_coerced() -> None:
    bad = json.loads(json.dumps(SAMPLE_PAYLOADS["CashOutObservationBatch"]))
    bad["items"][0]["channel"] = "UPI"  # not a member of Channel
    with pytest.raises(ValidationError):
        ingest.CashOutObservationBatch.model_validate(bad)


def test_complaint_time_order_rule() -> None:
    bad = json.loads(json.dumps(SAMPLE_PAYLOADS["ComplaintBatch"]))
    bad["items"][0]["observed_at"] = "2026-01-15T09:00:00+05:30"  # before reported_event_at
    with pytest.raises(ValidationError):
        ingest.ComplaintBatch.model_validate(bad)
