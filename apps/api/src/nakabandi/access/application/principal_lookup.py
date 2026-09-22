"""DOC 3 M5's `principal_from_request`, factored out from `nakabandi.access.__init__` so both
the facade (which re-exports it) and `access.interfaces.dependencies` (which uses it) can import
it without a circular import through the facade itself.
"""

from __future__ import annotations

from nakabandi.access.application.ports import TokenIssuer, UserRepo
from nakabandi.access.domain.principal import Principal, principal_for
from nakabandi.shared import Unauthenticated


def principal_from_token(token_issuer: TokenIssuer, user_repo: UserRepo, token: str) -> Principal:
    """Takes a UserRepo port and the raw cookie value rather than a Session and a FastAPI
    Request: this stays in `application` (ports only, never a concrete repository, DOC 2 §2.6
    layering) and framework-free. `access.interfaces.dependencies.get_principal` is the thin
    FastAPI dependency that builds a SqlUserRepo, extracts the cookie and calls this."""
    claims = token_issuer.decode(token)
    user = user_repo.get_by_id(claims.user_id)
    if user is None or not user.is_active:
        raise Unauthenticated("SESSION_INVALID", "sign in to continue")
    return principal_for(user)
