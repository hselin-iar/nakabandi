"""Principal and Scope (DOC 3 M5 FUNCTION & CLASS DESIGN). Pure: no I/O."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from nakabandi_contracts.enums import Role

from nakabandi.shared import Id

if TYPE_CHECKING:
    from nakabandi.access.domain.entities import User


@dataclass(frozen=True, slots=True)
class Scope:
    state_id: str | None = None
    district_id: str | None = None
    bank_id: str | None = None


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: Id
    role: Role
    scope: Scope
    display_name: str


def principal_for(user: User) -> Principal:
    """Always built fresh from the current User row, never trusted from a token's claims (DOC 3
    M5 edge case: "User deactivated while logged in: is_active is checked on each request" — a
    stale role or scope would go equally unnoticed if a token's own claims were trusted)."""
    return Principal(
        user_id=user.id,
        role=user.role,
        scope=Scope(
            state_id=user.scope_state_id,
            district_id=user.scope_district_id,
            bank_id=user.scope_bank_id,
        ),
        display_name=user.name,
    )
