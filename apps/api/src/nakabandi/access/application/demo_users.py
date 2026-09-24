"""Demo user seed data (DOC 3 M5: "demo users (one per role, demo-only passwords)"; DOC 2 §2.2:
"demo credentials are demo-only and never real"). Passwords are plaintext here BY DESIGN: they
are meant to be openly documented (this constant IS the documentation) and are never written to
the database in the clear — SeedDemoUsers hashes them before storing, and ListDemoUsers reads
the plaintext back from this constant, never from a stored value.
"""

from __future__ import annotations

from dataclasses import dataclass

from nakabandi_contracts.enums import Role

from nakabandi.access.domain.principal import Scope


@dataclass(frozen=True, slots=True)
class DemoUserSeed:
    name: str
    password: str
    role: Role
    scope: Scope
    locale: str


# Display names below are the fictional personas from data/seed/demo_users_seed.csv (a later
# data drop) so the login screen reads like real people rather than "Demo <Role>" placeholders.
# Scope ids and passwords are UNCHANGED from this file's own values, not the CSV's: the CSV's
# scope_bank_id ("BNK-001") and district codes use a real-data ID scheme that world-sim's
# synthetic registry (apps/world-sim/src/worldsim/core/registry.py) does not emit yet (it uses
# "SBI" not "BNK-001"), and changing scope ids here would break several tests that hardcode
# "demo-state-1"/"demo-district-1"/"demo-bank-1" directly. Full alignment needs world-sim's
# registry generation wired to the new data/seed CSVs first (Track B) — tracked separately, not
# done here. The CSV's 7th persona (Devendra Prasad, role "supervisor") has no matching Role enum
# member yet and is intentionally not included.
DEMO_USERS: tuple[DemoUserSeed, ...] = (
    DemoUserSeed("Aarav Kulkarni", "demo-i4c-2026", Role.I4C_ANALYST, Scope(), "en"),
    DemoUserSeed(
        "Ritu Verma",
        "demo-state-2026",
        Role.STATE_INVESTIGATOR,
        Scope(state_id="demo-state-1"),
        "en",
    ),
    DemoUserSeed(
        "Shadab Qureshi",
        "demo-district-2026",
        Role.DISTRICT_OFFICER,
        Scope(state_id="demo-state-1", district_id="demo-district-1"),
        "hi",
    ),
    DemoUserSeed(
        "Meena Iyer",
        "demo-bank-2026",
        Role.BANK_NODAL,
        Scope(bank_id="demo-bank-1"),
        "en",
    ),
    DemoUserSeed("Kabir Anand", "demo-operator-2026", Role.DEMO_OPERATOR, Scope(), "en"),
    DemoUserSeed("Nandini Bhosale", "demo-admin-2026", Role.ADMIN, Scope(), "en"),
)
