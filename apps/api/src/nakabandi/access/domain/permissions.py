"""authorize() (DOC 3 M5 FUNCTION & CLASS DESIGN). Pure: no I/O; the permission matrix (from
policy.yaml, LC-7) is passed in rather than read here, since Policy.load() is an I/O concern.
"""

from __future__ import annotations

from collections.abc import Mapping, Set

from nakabandi_contracts.enums import Permission, Role

from nakabandi.access.domain.principal import Principal, Scope
from nakabandi.shared import Forbidden


def authorize(
    principal: Principal,
    permission: Permission,
    role_permissions: Mapping[Role, Set[Permission]],
    resource_scope: Scope | None = None,
) -> None:
    """Raises Forbidden unless the principal's role holds `permission` (the matrix) and, if a
    resource scope is given, that scope lies inside the principal's own scope (DOC 3 M5:
    "district within state; bank equal"). A level the principal's own scope leaves unset (None)
    is unrestricted at that level; a level it does set must match the resource's own value at
    that same level, which the caller is responsible for populating accurately."""
    allowed = role_permissions.get(principal.role, frozenset())
    if permission not in allowed:
        raise Forbidden(
            "FORBIDDEN_PERMISSION",
            f"role {principal.role.value} does not hold permission {permission.value}",
        )
    if resource_scope is not None and not _scope_contains(principal.scope, resource_scope):
        raise Forbidden("FORBIDDEN_SCOPE", "the resource is outside the principal's scope")


def _scope_contains(principal_scope: Scope, resource_scope: Scope) -> bool:
    if principal_scope.bank_id is not None:
        return resource_scope.bank_id == principal_scope.bank_id
    if principal_scope.district_id is not None:
        return resource_scope.district_id == principal_scope.district_id
    if principal_scope.state_id is not None:
        return resource_scope.state_id == principal_scope.state_id
    return True
