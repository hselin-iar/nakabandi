"""A3 Evidence required: "the table list (matches DOC 3 LC-10 ownership)." Only geo and intake
are built so far; the remaining LC-10 tables land with their owning module's step."""

from __future__ import annotations

# Importing the model modules registers their tables on the shared Base.metadata.
import nakabandi.geo.infrastructure.models  # noqa: F401
import nakabandi.intake.infrastructure.models  # noqa: F401
from nakabandi.shared import Base

EXPECTED_TABLES = {
    # geo (LC-10)
    "regions",
    "banks",
    "locations",
    "cells",
    "units",
    # intake (LC-10)
    "accounts",
    "complaints",
    "fund_hops",
    "cashout_observations",
    "ingest_batches",
}


def test_table_list_matches_lc10_ownership_for_built_modules() -> None:
    assert set(Base.metadata.tables.keys()) == EXPECTED_TABLES
