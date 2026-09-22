#!/usr/bin/env python3
"""Regenerate packages/contracts/src/nakabandi_contracts/schemas/*.json from the Pydantic
models in ingest.py. Run via `npm run types` (or directly) after any LC-1 model change;
CI fails if this produces a diff, so the committed schemas never drift from the models.
"""

from __future__ import annotations

import json
from pathlib import Path

from nakabandi_contracts import ingest

_CONTRACTS_PKG = "packages/contracts/src/nakabandi_contracts"
SCHEMA_DIR = Path(__file__).resolve().parent.parent / _CONTRACTS_PKG / "schemas"

# The batch/response shapes are the ones other processes validate against (world-sim writer,
# bank-sim types, tests); the item and nested models are reachable through $defs.
TOP_LEVEL_MODELS = {
    "ComplaintBatch": ingest.ComplaintBatch,
    "HopBatch": ingest.HopBatch,
    "CashOutObservationBatch": ingest.CashOutObservationBatch,
    "RegistryUpdate": ingest.RegistryUpdate,
    "Tick": ingest.Tick,
    "IngestResponse": ingest.IngestResponse,
}


def main() -> None:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    for name, model in TOP_LEVEL_MODELS.items():
        schema = model.model_json_schema()
        out = SCHEMA_DIR / f"{name}.json"
        out.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
