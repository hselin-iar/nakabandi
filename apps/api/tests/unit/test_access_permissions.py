"""authorize() (DOC 3 M5 TESTING PLAN: "permission matrix (table-driven, every role x
permission)"). Table-driven against the REAL config/policy.yaml matrix, not a hand-copied one,
so this test catches drift between the two.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from nakabandi.access.domain.permissions import authorize
from nakabandi.access.domain.principal import Principal, Scope
from nakabandi.shared import Forbidden, Policy
from nakabandi_contracts.enums import Permission, Role

REPO_ROOT = Path(__file__).resolve().parents[4]
POLICY = Policy.load(REPO_ROOT / "config" / "policy.yaml")
ROLE_PERMISSIONS = {
    Role(role): frozenset(Permission(p) for p in perms)
    for role, perms in POLICY.access.permissions.items()
}


def _principal(role: Role) -> Principal:
    return Principal(user_id="u1", role=role, scope=Scope(), display_name="Test")


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize("permission", list(Permission))
def test_permission_matrix_every_role_x_permission(role: Role, permission: Permission) -> None:
    principal = _principal(role)
    if permission in ROLE_PERMISSIONS[role]:
        authorize(principal, permission, ROLE_PERMISSIONS)  # does not raise
    else:
        with pytest.raises(Forbidden):
            authorize(principal, permission, ROLE_PERMISSIONS)


def test_every_role_in_the_enum_has_a_policy_row() -> None:
    assert set(ROLE_PERMISSIONS) == set(Role)
