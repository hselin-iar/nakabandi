"""Enums only, no logic (DOC 3 Shared Kernel; values are LC-2, normative)."""

from enum import StrEnum


class Resolution(StrEnum):
    DISTRICT = "district"
    CELL = "cell"
    LOCATION = "location"


class Channel(StrEnum):
    """The channel a cash-out (or attempted cash-out) happens through."""

    ATM = "ATM"
    BRANCH = "BRANCH"
    AGENT = "AGENT"


class LocationKind(StrEnum):
    """The kind of a registry location. Same members as Channel (LC-2), kept as a
    separate enum because a location's kind and a transaction's channel are distinct
    concepts that happen to share a value set."""

    ATM = "ATM"
    BRANCH = "BRANCH"
    AGENT = "AGENT"


class ComplaintCategory(StrEnum):
    DIGITAL_ARREST = "digital_arrest"
    INVESTMENT_SCAM = "investment_scam"
    UPI_PHISHING = "upi_phishing"
    TASK_JOB_SCAM = "task_job_scam"


class Role(StrEnum):
    I4C_ANALYST = "i4c_analyst"
    STATE_INVESTIGATOR = "state_investigator"
    DISTRICT_OFFICER = "district_officer"
    BANK_NODAL = "bank_nodal"
    DEMO_OPERATOR = "demo_operator"
    ADMIN = "admin"


class AlertStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    ACTIONED = "actioned"
    ESCALATED = "escalated"
    EXPIRED = "expired"
    CLOSED = "closed"


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Verdict(StrEnum):
    INTERCEPTABLE = "INTERCEPTABLE"
    MARGINAL = "MARGINAL"
    NOT_INTERCEPTABLE = "NOT_INTERCEPTABLE"


class LadderLevel(StrEnum):
    NONE = "NONE"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class ActionType(StrEnum):
    ACKNOWLEDGE = "acknowledge"
    REQUEST_HOLD = "request_hold"
    NOTIFY_STATION = "notify_station"
    DISPATCH = "dispatch"
    OVERRIDE = "override"


class Permission(StrEnum):
    VIEW_ALERTS = "VIEW_ALERTS"
    ACKNOWLEDGE = "ACKNOWLEDGE"
    REQUEST_HOLD = "REQUEST_HOLD"
    NOTIFY_STATION = "NOTIFY_STATION"
    DISPATCH = "DISPATCH"
    OVERRIDE = "OVERRIDE"
    MARK_OUTCOME = "MARK_OUTCOME"
    CREATE_EVIDENCE = "CREATE_EVIDENCE"
    VIEW_CASES = "VIEW_CASES"
    VIEW_AUDIT = "VIEW_AUDIT"
    VIEW_EVALUATION = "VIEW_EVALUATION"
    SIM_CONTROL = "SIM_CONTROL"


class MetricName(StrEnum):
    HIT_RATE_AT_K = "hit_rate_at_k"
    PRECISION_AT_K = "precision_at_k"
    LEAD_TIME_MEDIAN = "lead_time_median"
    BRIER = "brier"
    INTERCEPTABLE_PRECISION = "interceptable_precision"
    INTERCEPTABLE_RECALL = "interceptable_recall"
    DISPATCHES_PER_INTERCEPTION = "dispatches_per_interception"
    FALSE_HOLD_RATE = "false_hold_rate"
    COLD_START_HIT_RATE = "cold_start_hit_rate"
    ABSTENTION_RATE = "abstention_rate"
