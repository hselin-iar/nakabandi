"""DomainError hierarchy and error code registry (DOC 3 Shared Kernel).

Raised by domain and application code, translated once in the interfaces layer to the error
JSON shape (DOC 2 §2.4). Developer detail goes to logs with the request id; the user-facing
text comes only from `messages.py`.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base of every domain error. `code` is a stable, upper-snake identifier; `details` holds
    structured, machine-readable extras (for example per-item validation failures)."""

    http_status: int = 500

    def __init__(self, code: str, message: str, details: list[dict] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details if details is not None else []


class ValidationFailed(DomainError):
    http_status = 422


class Unauthenticated(DomainError):
    http_status = 401


class Forbidden(DomainError):
    http_status = 403


class NotFound(DomainError):
    http_status = 404


class Conflict(DomainError):
    http_status = 409


class ExternalFailure(DomainError):
    """A downstream system failed (bank webhook, SMS provider, ...). Detail is internal only;
    never shown to a user verbatim (messages.py supplies the user-facing text)."""

    http_status = 502


class InvariantViolated(DomainError):
    """An invariant the code itself is supposed to guarantee did not hold. Always a bug."""

    http_status = 500
