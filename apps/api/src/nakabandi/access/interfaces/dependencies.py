"""get_principal (DOC 3 M5 MODULE STRUCTURE: "interfaces/ ... dependencies.py (get_principal)").
Re-exported through the facade so other modules' routers can depend on it without reaching into
`access.interfaces` directly (DOC 2 §2.6 facade rule).

No DOC names the session cookie's name; `nakabandi_session` is chosen here and documented as
the one place that names it (auth routers set it, this dependency reads it).
"""

from __future__ import annotations

from fastapi import Request

from nakabandi.access.application.principal_lookup import principal_from_token
from nakabandi.access.domain.principal import Principal
from nakabandi.access.infrastructure.user_repo import SqlUserRepo
from nakabandi.shared import Unauthenticated

SESSION_COOKIE_NAME = "nakabandi_session"


def get_principal(request: Request) -> Principal:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is None:
        raise Unauthenticated("SESSION_MISSING", "sign in to continue")

    with request.app.state.session_factory() as db_session:
        user_repo = SqlUserRepo(db_session)
        return principal_from_token(request.app.state.token_issuer, user_repo, token)
