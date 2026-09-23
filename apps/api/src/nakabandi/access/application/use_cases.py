"""Login, Logout, SeedDemoUsers, CheckRole, ListDemoUsers (DOC 3 M5 FUNCTION & CLASS DESIGN).

Login and logout are audited via the audit facade (DOC 3 M5: "The audit facade is called from
alerting, casework and access"); the append shares the caller's transaction (LC-9).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from nakabandi_contracts.enums import Role

from nakabandi.access.application.demo_users import DEMO_USERS
from nakabandi.access.application.ports import PasswordHasher, TokenIssuer, UserRepo
from nakabandi.access.application.session import Session
from nakabandi.access.domain.entities import User
from nakabandi.access.domain.principal import Principal, principal_for
from nakabandi.audit import AuditLog
from nakabandi.shared import SystemClock, Unauthenticated, new_id

SESSION_TTL = timedelta(hours=12)
"""Not in LC-7 (no access.session_ttl key): DOC 3 M5 names a JWT cookie with an `exp` claim but
no lifetime value. A Track-A-authored starting value, same status as config/policy.yaml's
unmarked seeds (docs/state/track-a.md Learnings)."""

_LOGIN_FAILED_MESSAGE = "invalid username or password"
"""One message for both an unknown user and a wrong password (DOC 3 M5 ERROR HANDLING
STRATEGY): never reveal which one it was."""


class Login:
    def __init__(
        self,
        user_repo: UserRepo,
        hasher: PasswordHasher,
        tokens: TokenIssuer,
        audit: AuditLog,
    ) -> None:
        self._users = user_repo
        self._hasher = hasher
        self._tokens = tokens
        self._audit = audit

    def run(self, name: str, password: str) -> Session:
        user = self._users.get_by_name(name)
        ok = (
            user is not None
            and user.is_active
            and self._hasher.verify(password, user.password_hash)
        )
        if not ok:
            self._audit.append(
                actor_id=user.id if user is not None else "unknown",
                actor_role=user.role.value if user is not None else "unknown",
                action="login_failed",
                entity_type="user",
                entity_id=user.id if user is not None else name,
                payload={"name": name},
            )
            raise Unauthenticated("LOGIN_FAILED", _LOGIN_FAILED_MESSAGE)

        assert user is not None
        # Wall-clock, not the injected (possibly simulated) clock: a cookie/JWT's expiry is a
        # transport-level lifetime a real browser and a real JWT library enforce in real time,
        # like LC-6's webhook timestamp window (DOC 2 §2.4) — never the simulated timeline.
        expires_at = SystemClock().now() + SESSION_TTL
        token = self._tokens.issue(user, expires_at)
        self._audit.append(
            actor_id=user.id,
            actor_role=user.role.value,
            action="login_succeeded",
            entity_type="user",
            entity_id=user.id,
            payload={},
        )
        principal = principal_for(user)
        return Session(token=token, expires_at=expires_at, principal=principal)


class Logout:
    def __init__(self, audit: AuditLog) -> None:
        self._audit = audit

    def run(self, principal: Principal) -> None:
        self._audit.append(
            actor_id=principal.user_id,
            actor_role=principal.role.value,
            action="logout",
            entity_type="user",
            entity_id=principal.user_id,
            payload={},
        )


class CheckRole:
    def run(self, principal: Principal, role: Role) -> bool:
        return principal.role == role


class SeedDemoUsers:
    def __init__(self, user_repo: UserRepo, hasher: PasswordHasher) -> None:
        self._users = user_repo
        self._hasher = hasher

    def run(self) -> list[User]:
        created: list[User] = []
        for seed in DEMO_USERS:
            if self._users.get_by_name(seed.name) is not None:
                continue
            user = User(
                id=new_id(),
                name=seed.name,
                role=seed.role,
                scope_state_id=seed.scope.state_id,
                scope_district_id=seed.scope.district_id,
                scope_bank_id=seed.scope.bank_id,
                password_hash=self._hasher.hash(seed.password),
                locale=seed.locale,
                is_active=True,
            )
            self._users.add(user)
            created.append(user)
        return created


@dataclass(frozen=True, slots=True)
class DemoUserInfo:
    name: str
    password: str
    role: Role
    display_name: str


class ListDemoUsers:
    def __init__(self, user_repo: UserRepo) -> None:
        self._users = user_repo

    def run(self) -> list[DemoUserInfo]:
        return [
            DemoUserInfo(
                name=seed.name, password=seed.password, role=seed.role, display_name=seed.name
            )
            for seed in DEMO_USERS
            if self._users.get_by_name(seed.name) is not None
        ]
