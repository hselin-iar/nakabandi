"""mask_ref() (DOC 3 M5 FUNCTION & CLASS DESIGN). Pure: no I/O.

bank_nodal shows a ref in full, but only ever for its OWN bank: the repository is responsible
for filtering out every other bank's rows before a bank_nodal principal's request ever reaches
this function (DOC 3 M5: "never returned for other banks, the repository filters first")."""

from __future__ import annotations

from nakabandi_contracts.enums import Role

from nakabandi.access.domain.principal import Principal

_FULL_ACCESS_ROLES = frozenset(
    {Role.I4C_ANALYST, Role.STATE_INVESTIGATOR, Role.ADMIN, Role.BANK_NODAL}
)


def mask_ref(ref: str, principal: Principal) -> str:
    if principal.role in _FULL_ACCESS_ROLES:
        return ref
    if principal.role == Role.DISTRICT_OFFICER:
        return f"****{ref[-4:]}" if len(ref) > 4 else "****"
    return "***"
