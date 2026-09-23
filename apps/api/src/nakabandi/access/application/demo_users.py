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


DEMO_USERS: tuple[DemoUserSeed, ...] = (
    DemoUserSeed("Demo I4C Analyst", "demo-i4c-2026", Role.I4C_ANALYST, Scope(), "en"),
    DemoUserSeed(
        "Demo State Investigator",
        "demo-state-2026",
        Role.STATE_INVESTIGATOR,
        Scope(state_id="demo-state-1"),
        "en",
    ),
    DemoUserSeed(
        "Demo District Officer",
        "demo-district-2026",
        Role.DISTRICT_OFFICER,
        Scope(state_id="demo-state-1", district_id="demo-district-1"),
        "hi",
    ),
    DemoUserSeed(
        "Demo Bank Nodal Officer",
        "demo-bank-2026",
        Role.BANK_NODAL,
        Scope(bank_id="demo-bank-1"),
        "en",
    ),
    DemoUserSeed("Demo Operator", "demo-operator-2026", Role.DEMO_OPERATOR, Scope(), "en"),
    DemoUserSeed("Demo Admin", "demo-admin-2026", Role.ADMIN, Scope(), "en"),
)
