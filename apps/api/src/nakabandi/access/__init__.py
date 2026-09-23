"""Public facade of the access module: what other modules may import (DOC 3).

AccessService is constructed on the caller's active SQLAlchemy session (like intake's
IngestService and geo's GeoService), so a login and its audit entry share one transaction
(LC-9). `authorize` and `mask_ref` are also exposed as the bare pure functions DOC 3 M5 names,
since neither needs a session.
"""

from __future__ import annotations

from collections.abc import Mapping, Set

from nakabandi_contracts.enums import Permission, Role
from sqlalchemy.orm import Session

from nakabandi.access.application.demo_users import DemoUserSeed
from nakabandi.access.application.ports import TokenIssuer
from nakabandi.access.application.principal_lookup import principal_from_token
from nakabandi.access.application.session import Session as LoginSession
from nakabandi.access.application.use_cases import (
    CheckRole,
    DemoUserInfo,
    ListDemoUsers,
    Login,
    Logout,
    SeedDemoUsers,
)
from nakabandi.access.domain.entities import User
from nakabandi.access.domain.masking import mask_ref
from nakabandi.access.domain.permissions import authorize
from nakabandi.access.domain.principal import Principal, Scope
from nakabandi.access.infrastructure.password import Argon2PasswordHasher
from nakabandi.access.infrastructure.user_repo import SqlUserRepo
from nakabandi.access.interfaces.dependencies import SESSION_COOKIE_NAME, get_principal
from nakabandi.audit import AuditLog
from nakabandi.shared import Clock

__all__ = [
    "AccessService",
    "Principal",
    "Scope",
    "Role",
    "Permission",
    "DemoUserInfo",
    "DemoUserSeed",
    "User",
    "authorize",
    "mask_ref",
    "principal_from_token",
    "get_principal",
    "SESSION_COOKIE_NAME",
]


class AccessService:
    def __init__(
        self,
        session: Session,
        clock: Clock,
        token_issuer: TokenIssuer,
        role_permissions: Mapping[Role, Set[Permission]],
    ) -> None:
        user_repo = SqlUserRepo(session)
        hasher = Argon2PasswordHasher()
        audit = AuditLog(session, clock)

        self._login = Login(user_repo, hasher, token_issuer, audit)
        self._logout = Logout(audit)
        self._check_role = CheckRole()
        self._seed_demo_users = SeedDemoUsers(user_repo, hasher)
        self._list_demo_users = ListDemoUsers(user_repo)
        self._role_permissions = role_permissions

    def login(self, username: str, password: str) -> LoginSession:
        return self._login.run(username, password)

    def logout(self, principal: Principal) -> None:
        self._logout.run(principal)

    def check_role(self, principal: Principal, role: Role) -> bool:
        return self._check_role.run(principal, role)

    def seed_demo_users(self) -> list[User]:
        return self._seed_demo_users.run()

    def list_demo_users(self) -> list[DemoUserInfo]:
        return self._list_demo_users.run()

    def permissions_for(self, role: Role) -> Set[Permission]:
        return self._role_permissions.get(role, frozenset())

    def authorize(
        self, principal: Principal, permission: Permission, resource_scope: Scope | None = None
    ) -> None:
        authorize(principal, permission, self._role_permissions, resource_scope)
