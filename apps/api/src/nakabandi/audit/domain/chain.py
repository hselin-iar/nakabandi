"""canonical_json(), compute_hash(), verify_chain() (DOC 3 M5 FUNCTION & CLASS DESIGN). Pure.

hash = SHA256(prev_hash || canonical_json(entry content)), where "entry content" is every
AuditEntry field except `prev_hash` and `hash` themselves (DOC 3 M5: "hash = SHA256(prev_hash
|| canonical_json(entry without hash))" — read as "without the two chain-linking fields",
the standard hash-chain shape: each link's hash is a function of the previous link's hash plus
this link's own content, never of itself).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from nakabandi.audit.domain.entities import AuditEntry

GENESIS_HASH = "0" * 64
"""prev_hash of the first entry (seq 1): no real entry ever produces this value as its own
hash, so a chain that claims to start elsewhere is visibly wrong."""


def entry_content(entry: AuditEntry) -> dict:
    """Every field except prev_hash and hash, in a JSON-safe shape."""
    return {
        "seq": entry.seq,
        "at": entry.at.isoformat(),
        "actor_id": entry.actor_id,
        "actor_role": entry.actor_role,
        "action": entry.action,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "reason": entry.reason,
        "payload": entry.payload,
    }


def canonical_json(content: dict) -> str:
    return json.dumps(content, sort_keys=True, separators=(",", ":"))


def compute_hash(prev_hash: str, content: dict) -> str:
    return hashlib.sha256((prev_hash + canonical_json(content)).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class VerifyReport:
    ok: bool
    first_bad_seq: int | None
    head_hash: str | None


def verify_chain(entries: list[AuditEntry]) -> VerifyReport:
    """`entries` must be given in ascending seq order."""
    prev_hash = GENESIS_HASH
    for entry in entries:
        expected = compute_hash(prev_hash, entry_content(entry))
        if entry.prev_hash != prev_hash or entry.hash != expected:
            return VerifyReport(ok=False, first_bad_seq=entry.seq, head_hash=prev_hash)
        prev_hash = entry.hash
    return VerifyReport(
        ok=True, first_bad_seq=None, head_hash=prev_hash if entries else GENESIS_HASH
    )
