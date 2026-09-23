"""Session: the result of a successful login (DOC 3 M5: "Login.run(username, password) ->
Session")."""

from __future__ import annotations

from dataclasses import dataclass

from nakabandi.access.domain.principal import Principal
from nakabandi.shared import SimTime


@dataclass(frozen=True, slots=True)
class Session:
    token: str
    expires_at: SimTime
    principal: Principal
