"""Repository and infrastructure ports for access (DOC 3 LC-9)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from nakabandi_contracts.enums import Role

from nakabandi.access.domain.entities import User
from nakabandi.access.domain.principal import Scope
from nakabandi.shared import Id, SimTime


class UserRepo(Protocol):
    def get_by_name(self, name: str) -> User | None: ...
    def get_by_id(self, user_id: Id) -> User | None: ...
    def add(self, user: User) -> None: ...
    def list_all(self) -> list[User]: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...
    def verify(self, password: str, password_hash: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class TokenClaims:
    user_id: Id
    role: Role
    scope: Scope
    expires_at: SimTime


class TokenIssuer(Protocol):
    def issue(self, user: User, expires_at: SimTime) -> str: ...

    def decode(self, token: str) -> TokenClaims:
        """Raises Unauthenticated on an expired, malformed or badly signed token."""
        ...
