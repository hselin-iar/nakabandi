"""structlog setup: JSON logs to stdout, a scrub processor, and request-id context
(DOC 3 Shared Kernel; DOC 2 §2.7 security: "Logs never contain account_ref, tokens or
passwords")."""

from __future__ import annotations

from typing import Any

import structlog
from structlog.typing import EventDict

# Field names that must never reach a log line in the clear. Matched case-insensitively
# against event_dict keys; nested dict/list values are scrubbed recursively.
_SENSITIVE_KEYS = {
    "account_ref",
    "password",
    "token",
    "secret",
    "authorization",
    "cookie",
    "webhook_secret",
    "api_service_key",
}
_REDACTED = "***"


def _scrub(_logger: object, _method_name: str, event_dict: EventDict) -> EventDict:
    def scrub_key_value(key: str, value: Any) -> Any:
        return _REDACTED if key.lower() in _SENSITIVE_KEYS else scrub_value(value)

    def scrub_value(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: scrub_key_value(k, v) for k, v in value.items()}
        if isinstance(value, list):
            return [scrub_value(v) for v in value]
        return value

    return {k: scrub_key_value(k, v) for k, v in event_dict.items()}


def bind_request_id(request_id: str) -> None:
    """Attach a request id to every log line emitted on this logical thread/task until cleared."""
    structlog.contextvars.bind_contextvars(request_id=request_id)


def clear_request_context() -> None:
    structlog.contextvars.clear_contextvars()


def configure_logging(*, json: bool = True) -> None:
    """Call once at process startup (main.py). JSON to stdout in every environment except when
    `json=False` is passed for local, human-readable development output."""
    renderer = structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _scrub,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
        cache_logger_on_first_use=True,
    )
