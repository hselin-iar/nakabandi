"""npm run seed: loads a JSONL file through the SAME intake use cases as the HTTP routers
(DOC 4 Step A3 "What to build": "no bypass"). Each line is `{"kind": ..., "payload": ...}`;
`kind` is one of registry | complaints | hops | cashout_observations | tick.

Usage: uv run python scripts/seed.py [--file data/seed/mini_ingest.jsonl]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nakabandi.intake import IngestService
from nakabandi.shared import SIM_CLOCK_EPOCH, SimClock, SqlAlchemyUnitOfWork, get_settings
from nakabandi.shared.infrastructure.db import (
    create_all,
    create_sqlite_engine,
    make_session_factory,
)
from nakabandi_contracts.ingest import (
    CashOutObservationBatch,
    ComplaintBatch,
    HopBatch,
    RegistryUpdate,
    Tick,
)

_PAYLOAD_MODEL = {
    "registry": RegistryUpdate,
    "complaints": ComplaintBatch,
    "hops": HopBatch,
    "cashout_observations": CashOutObservationBatch,
    "tick": Tick,
}

_SERVICE_METHOD = {
    "registry": "ingest_registry",
    "complaints": "ingest_complaints",
    "hops": "ingest_hops",
    "cashout_observations": "ingest_observations",
    "tick": "advance_clock",
}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=Path("data/seed/mini_ingest.jsonl"))
    args = parser.parse_args(argv)

    settings = get_settings()
    engine = create_sqlite_engine(settings.database_url)
    create_all(engine)
    session_factory = make_session_factory(engine)
    clock = SimClock(start=SIM_CLOCK_EPOCH)

    lines = args.file.read_text().splitlines()
    for line_no, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        kind = record["kind"]
        if kind not in _PAYLOAD_MODEL:
            print(f"{args.file}:{line_no}: unknown kind {kind!r}", file=sys.stderr)
            return 1

        model = _PAYLOAD_MODEL[kind]
        payload = model.model_validate(record["payload"])
        with SqlAlchemyUnitOfWork(session_factory) as uow:
            assert uow.session is not None
            service = IngestService(uow.session, clock)
            response = getattr(service, _SERVICE_METHOD[kind])(payload)
            uow.commit()
        print(
            f"{args.file}:{line_no}: {kind} -> accepted={response.accepted} "
            f"rejected={len(response.rejected)} sim_time={response.sim_time.isoformat()}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
