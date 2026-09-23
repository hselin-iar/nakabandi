"""DOC 3 M5 TESTING PLAN, Property: "a bank_nodal principal never receives an identifier of
another bank across randomised alert sets." mask_ref only ever runs on a row the repository has
already scoped (DOC 3 M5: "the repository filters first"), so the guarantee that actually
belongs to this module is authorize()'s scope check: across randomised (principal scope,
resource scope) pairs, a bank_nodal (or district_officer, or state_investigator) principal is
authorized for a resource only when that resource's own identifier at the principal's scope
level matches — never for a different bank, district or state.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from nakabandi.access.domain.permissions import authorize
from nakabandi.access.domain.principal import Principal, Scope
from nakabandi.shared import Forbidden
from nakabandi_contracts.enums import Permission, Role

_IDS = st.sampled_from(["a", "b", "c"])
_ALLOW_ALL = {Role.BANK_NODAL: frozenset({Permission.VIEW_ALERTS})}


@given(principal_bank=_IDS, resource_bank=_IDS)
def test_bank_nodal_never_authorized_for_another_banks_resource(
    principal_bank: str, resource_bank: str
) -> None:
    principal = Principal(
        user_id="u1", role=Role.BANK_NODAL, scope=Scope(bank_id=principal_bank), display_name="B"
    )
    resource_scope = Scope(bank_id=resource_bank)

    if principal_bank == resource_bank:
        authorize(principal, Permission.VIEW_ALERTS, _ALLOW_ALL, resource_scope)  # no raise
    else:
        with pytest.raises(Forbidden):
            authorize(principal, Permission.VIEW_ALERTS, _ALLOW_ALL, resource_scope)
