"""Alert entity and state machine (DOC 3 M4 — pure, no I/O).

LC-10: alerting owns the alerts and alert_timeline tables.
LC-4:  AlertSummary / AlertDetail field lists are derived from this entity.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from nakabandi_contracts.enums import AlertStatus, LadderLevel, Severity

from nakabandi.shared import Conflict, Id, SimTime

# ---------------------------------------------------------------------------
# State machine (DOC 3 M4: "State machine is a transition table; anything
# else raises Conflict")
# ---------------------------------------------------------------------------

_TRANSITIONS: dict[AlertStatus, set[AlertStatus]] = {
    AlertStatus.OPEN: {
        AlertStatus.ACKNOWLEDGED,
        AlertStatus.ACTIONED,
        AlertStatus.ESCALATED,
        AlertStatus.EXPIRED,
    },
    AlertStatus.ESCALATED: {
        AlertStatus.ACKNOWLEDGED,
        AlertStatus.ACTIONED,
        AlertStatus.EXPIRED,
    },
    AlertStatus.ACKNOWLEDGED: {
        AlertStatus.ACTIONED,
        AlertStatus.CLOSED,
        AlertStatus.EXPIRED,
    },
    AlertStatus.ACTIONED: {
        AlertStatus.CLOSED,
    },
    # Terminal states — no outgoing transitions
    AlertStatus.EXPIRED: set(),
    AlertStatus.CLOSED: set(),
}


# A human may still act on an alert in these states (RecordAction, and what the UI offers).
ACTIONABLE_STATUSES = frozenset({AlertStatus.OPEN, AlertStatus.ESCALATED, AlertStatus.ACKNOWLEDGED})


# ---------------------------------------------------------------------------
# Timeline entry (pure; mapped to ORM in infrastructure)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class TimelineEntry:
    id: Id
    alert_id: Id
    at: SimTime
    kind: str  # raised | merged | escalated | expired | acknowledged | actioned | closed
    actor_id: Id | None
    text_code: str
    text_params: dict


# ---------------------------------------------------------------------------
# Alert entity (pure domain object; ORM model lives in infrastructure)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Alert:
    id: Id
    cluster_ref: Id  # cluster_id that generated this alert
    target_kind: str  # LocationKind value (ATM | BRANCH | AGENT)
    target_id: Id  # location_id
    target_name: str
    dedup_key: str
    severity: Severity
    confidence: float
    status: AlertStatus
    ladder_level: LadderLevel
    is_deferred: bool
    is_probe: bool
    window_start: SimTime
    window_end: SimTime
    expires_at: SimTime
    created_at: SimTime
    forecast_id: Id  # most-recent forecast that contributed
    complaint_id: Id  # the complaint anchor: the complaint whose forecast raised this alert
    masked: bool = False
    # Where the target location sits, copied at raise time so the alert can be filtered by a
    # principal's scope without reading geo (DOC 2 §2.3 Alert.scope_*; state added because
    # authorize() compares a state-scoped principal against the resource's state).
    scope_state_id: str | None = None
    scope_district_id: str | None = None
    scope_bank_id: str | None = None
    # DOC 3 M4 budget: priority = confidence x log1p(amount) x interception_probability, fixed at
    # raise time; budget_rank is the alert's place (1 = first) in its queue for its shift.
    priority: float = 0.0
    budget_rank: int | None = None
    timeline: list[TimelineEntry] = field(default_factory=list)

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def transition(self, new_status: AlertStatus, entry: TimelineEntry) -> None:
        """Attempt a state transition; raises Conflict on illegal moves."""
        allowed = _TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise Conflict(
                "INVALID_TRANSITION",
                f"Cannot move alert from {self.status.value!r} to {new_status.value!r}",
                details=[{"from": self.status.value, "to": new_status.value}],
            )
        self.status = new_status
        self.timeline.append(entry)

    # ------------------------------------------------------------------
    # Merge (DOC 3 M4 RaiseOrMergeAlert: keep earlier created_at, update
    # confidence and window_end if the new values extend/improve them)
    # ------------------------------------------------------------------

    def merge(
        self,
        *,
        forecast_id: Id,
        confidence: float,
        window_end: SimTime,
        entry: TimelineEntry,
    ) -> None:
        """Merge a new forecast into an open alert (confidence rises / window extends)."""
        self.forecast_id = forecast_id
        self.confidence = max(self.confidence, confidence)
        if window_end > self.window_end:
            self.window_end = window_end
        self.timeline.append(entry)
