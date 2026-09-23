"""User-facing text per error code, kept separate from developer detail (DOC 3 Shared Kernel).

Modules add their own codes here as they are built (for example FORBIDDEN_ACTION,
INVALID_TRANSITION, LIEN_INVALID land with M4/M6). This file seeds only the generic codes
tied to the DomainError subclasses in errors.py, plus a safe fallback.
"""

from __future__ import annotations

FALLBACK_MESSAGE = "Something went wrong. Please try again or contact support."

MESSAGES: dict[str, str] = {
    "VALIDATION_FAILED": "Some of the information provided is not valid.",
    "UNAUTHENTICATED": "Please sign in to continue.",
    "FORBIDDEN": "You do not have permission to do this.",
    "NOT_FOUND": "We could not find what you were looking for.",
    "CONFLICT": "This could not be completed because of a conflicting change.",
    "EXTERNAL_FAILURE": "A connected service is unavailable right now. Please try again shortly.",
    "INVARIANT_VIOLATED": FALLBACK_MESSAGE,
    "SIM_TIME_NAIVE": "An internal timestamp was invalid.",
    "NEGATIVE_AMOUNT": "An amount cannot be negative.",
}


def message_for(code: str) -> str:
    """The text a user may see for an error code. Never raises; falls back to a generic message
    so an unmapped code still shows something safe rather than a stack trace."""
    return MESSAGES.get(code, FALLBACK_MESSAGE)
