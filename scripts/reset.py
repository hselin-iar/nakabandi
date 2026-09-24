"""npm run reset: restore the seeded database, offline (DOC 4 A11: "nightly reset job restoring
the seeded database"; DOC 2 §2.7: "database size capped by reset").

    uv run python scripts/reset.py [--seed-file data/seed/mini_ingest.jsonl]

Drops every table in DATABASE_URL, recreates them, puts the demo users back and reloads the seed
file through the same intake use cases the HTTP routes use. STOP THE API FIRST: this is the
offline path. A running hosted API does the same every night itself (NAKABANDI_NIGHTLY_RESET_AT,
or 03:00 UTC with NAKABANDI_HOSTED_DEMO=true) and needs no restart."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from nakabandi.access import AccessService
from nakabandi.access.infrastructure.tokens import JwtTokenIssuer
from nakabandi.main import _role_permissions
from nakabandi.maintenance import reset_database
from nakabandi.shared import SIM_CLOCK_EPOCH, Policy, SimClock, get_settings
from nakabandi.shared.infrastructure.db import create_sqlite_engine, make_session_factory


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-file", type=Path, default=None)
    args = parser.parse_args(argv)

    settings = get_settings()
    policy = Policy.load(settings.policy_path)
    engine = create_sqlite_engine(settings.database_url)
    clock = SimClock(start=SIM_CLOCK_EPOCH)
    role_permissions = _role_permissions(policy)
    issuer = JwtTokenIssuer(settings.jwt_secret)

    report = reset_database(
        engine,
        make_session_factory(engine),
        clock,
        args.seed_file or settings.seed_file,
        lambda session: AccessService(session, clock, issuer, role_permissions).seed_demo_users(),
    )
    print(
        f"reset {settings.database_url}: {report.seed_lines} seed lines, "
        f"{report.accepted} records accepted, {report.rejected} rejected"
    )
    return 1 if report.rejected else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
