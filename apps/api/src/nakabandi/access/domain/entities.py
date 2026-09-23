"""User entity (DOC 2 §2.3 CORE ENTITIES, access section; DOC 3 LC-10: access owns users).

DOC 2's field list has no separate `username`; DOC 3 M5's `Login.run(username, password)`
matches against `name` (unique for this purpose), rather than adding a column DOC 2 does not
name (AP-08 Schema Drift).
"""

from __future__ import annotations

from dataclasses import dataclass

from nakabandi_contracts.enums import Role

from nakabandi.shared import Id


@dataclass(slots=True)
class User:
    id: Id
    name: str
    role: Role
    scope_state_id: str | None
    scope_district_id: str | None
    scope_bank_id: str | None
    password_hash: str
    locale: str  # "en" | "hi"
    is_active: bool
