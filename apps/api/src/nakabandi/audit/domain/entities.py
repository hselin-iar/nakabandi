"""AuditEntry (DOC 2 §2.3 CORE ENTITIES; DOC 3 M5 INTERFACES & CONTRACTS)."""

from __future__ import annotations

from dataclasses import dataclass

from nakabandi.shared import Id, SimTime


@dataclass(frozen=True, slots=True)
class AuditEntry:
    seq: int
    at: SimTime
    actor_id: Id
    actor_role: str
    action: str
    entity_type: str
    entity_id: Id
    reason: str | None
    payload: dict
    prev_hash: str
    hash: str
