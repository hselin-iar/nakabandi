"""User-facing text per error code, kept separate from developer detail (DOC 3 Shared Kernel).

Modules add their own codes here as they are built (for example FORBIDDEN_ACTION,
INVALID_TRANSITION, LIEN_INVALID land with M4/M6). This file seeds the generic codes tied to
the DomainError subclasses in errors.py, the codes intake/geo (Step A3) and access/audit
(Step A4) raise, and a safe fallback.
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
    # intake / geo (Step A3)
    "COMPLAINT_AMOUNT_NOT_POSITIVE": "The reported amount must be greater than zero.",
    "COMPLAINT_TIME_ORDER": "The reported times for this complaint are out of order.",
    "COMPLAINT_LAYER1_ACCOUNT_MISSING": "A first-layer account is required for this complaint.",
    "HOP_UNKNOWN_COMPLAINT": "This transfer does not reference a known complaint.",
    "ACCOUNT_UNKNOWN": "This account is not yet known to the system.",
    "GEO_BANK_MISSING_FIELD": "A required field is missing from a bank entry.",
    "GEO_REGION_MISSING_FIELD": "A required field is missing from a region entry.",
    "GEO_CELL_MISSING_FIELD": "A required field is missing from a cell entry.",
    "GEO_REGION_INVALID_LEVEL": "A region's level must be 'state' or 'district'.",
    "GEO_BANK_INTEGRITY": "This bank entry conflicts with existing registry data.",
    "GEO_REGION_INTEGRITY": "This region entry conflicts with existing registry data.",
    "GEO_CELL_INTEGRITY": "This cell entry conflicts with existing registry data.",
    "GEO_LOCATION_INTEGRITY": "This location entry conflicts with existing registry data.",
    "GEO_UNIT_INTEGRITY": "This unit entry conflicts with existing registry data.",
    "SERVICE_KEY_INVALID": "This request could not be authenticated.",
    # access / audit (Step A4)
    "LOGIN_FAILED": "Invalid username or password.",
    "SESSION_MISSING": "Please sign in to continue.",
    "SESSION_INVALID": "Your session has expired. Please sign in again.",
    "TOKEN_INVALID": "Your session has expired. Please sign in again.",
    "FORBIDDEN_PERMISSION": "You do not have permission to do this.",
    "FORBIDDEN_SCOPE": "This is outside your assigned scope.",
    "ROLE_MISMATCH": "You do not hold the required role for this action.",
    # alerting (Step A7)
    "ALERT_NOT_FOUND": "This alert could not be found.",
    "INVALID_TRANSITION": "This action is not allowed for the alert's current status.",
    "FORBIDDEN_ACTION": "You do not have permission to perform this action on this alert.",
    "LIEN_INVALID": "The proposed hold amount is invalid.",
    # alerting delivery, actions and callbacks (Step A8)
    "LIEN_EXCEEDS_REMAINING": "The proposed hold is above what can still be held.",
    "LIEN_ACCOUNT_NOT_TRACED": "This account is not part of the traced funds for this complaint.",
    "ACTION_REASON_REQUIRED": "A reason is required for this action.",
    "ACTION_NOT_FOUND": "This request could not be found.",
    "CALLBACK_INVALID": "The bank's update could not be accepted.",
}


def message_for(code: str) -> str:
    """The text a user may see for an error code. Never raises; falls back to a generic message
    so an unmapped code still shows something safe rather than a stack trace."""
    return MESSAGES.get(code, FALLBACK_MESSAGE)
