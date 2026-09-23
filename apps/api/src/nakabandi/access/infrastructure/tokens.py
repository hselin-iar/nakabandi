"""JwtTokenIssuer (DOC 2 §2.2: "Login issues a signed JWT"). PyJWT is the standard Python JWT
library; DOC 2 names the technique, not a package, so no library choice was left open here."""

from __future__ import annotations

from datetime import UTC, datetime

import jwt
from nakabandi_contracts.enums import Role

from nakabandi.access.application.ports import TokenClaims
from nakabandi.access.domain.entities import User
from nakabandi.access.domain.principal import Scope
from nakabandi.shared import SimTime, Unauthenticated

_ALGORITHM = "HS256"


class JwtTokenIssuer:
    def __init__(self, secret: str) -> None:
        self._secret = secret

    def issue(self, user: User, expires_at: SimTime) -> str:
        claims = {
            "sub": user.id,
            "role": user.role.value,
            "scope": {
                "state_id": user.scope_state_id,
                "district_id": user.scope_district_id,
                "bank_id": user.scope_bank_id,
            },
            "exp": int(expires_at.timestamp()),
        }
        return jwt.encode(claims, self._secret, algorithm=_ALGORITHM)

    def decode(self, token: str) -> TokenClaims:
        try:
            claims = jwt.decode(token, self._secret, algorithms=[_ALGORITHM])
        except jwt.PyJWTError as exc:
            raise Unauthenticated("TOKEN_INVALID", "session expired or invalid") from exc
        scope = claims.get("scope") or {}
        return TokenClaims(
            user_id=claims["sub"],
            role=Role(claims["role"]),
            scope=Scope(
                state_id=scope.get("state_id"),
                district_id=scope.get("district_id"),
                bank_id=scope.get("bank_id"),
            ),
            expires_at=datetime.fromtimestamp(claims["exp"], tz=UTC),
        )
