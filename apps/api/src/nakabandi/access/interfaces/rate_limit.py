"""Login rate limiting (DOC 3 M5 ERROR HANDLING STRATEGY: "Login is rate limited (5 per minute
per IP) with 429"). Wall-clock, not SimClock: like LC-6's webhook timestamp window, this is a
transport-level abuse control, not a simulated-time domain event (DOC 2 §2.4).

State lives on `app.state` (one dict per app instance, not a module-level global) so a fresh
`create_app()` — as every test in this codebase makes for its own isolated app — starts with a
clean rate limiter instead of inheriting attempt counts from every other test in the process
(DOC 2 §2.2: single Uvicorn worker, so one process-wide app instance is exactly what runs in
production; this only matters for keeping tests independent).
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import timedelta

from fastapi import HTTPException, Request

from nakabandi.shared import SystemClock

MAX_ATTEMPTS_PER_WINDOW = 5
WINDOW = timedelta(minutes=1)
"""Not in LC-7 (no access.login_rate_limit key): DOC 3 M5 states this number directly in prose,
not as a policy.<x> reference the way LC-7's tunables are. Flagged for the Integration Owner in
case it should become an LC-7 addition (docs/state/track-a.md Learnings)."""


class LoginAttempts:
    def __init__(self) -> None:
        self._by_ip: dict[str, deque] = defaultdict(deque)

    def check(self, ip: str) -> None:
        now = SystemClock().now()
        attempts = self._by_ip[ip]
        while attempts and now - attempts[0] > WINDOW:
            attempts.popleft()
        if len(attempts) >= MAX_ATTEMPTS_PER_WINDOW:
            raise HTTPException(
                status_code=429, detail="too many login attempts; try again shortly"
            )
        attempts.append(now)


def enforce_login_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    request.app.state.login_attempts.check(ip)
