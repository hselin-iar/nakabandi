"""canonical_json, compute_hash, verify_chain (DOC 3 M5 TESTING PLAN: "compute_hash and
verify_chain detect a modified payload, deletion and reorder")."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from nakabandi.audit.domain.chain import (
    GENESIS_HASH,
    canonical_json,
    compute_hash,
    entry_content,
    verify_chain,
)
from nakabandi.audit.domain.entities import AuditEntry

NOW = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)


def _entry(seq: int, prev_hash: str, action: str = "login_succeeded") -> AuditEntry:
    content = {
        "seq": seq,
        "at": NOW.isoformat(),
        "actor_id": "u1",
        "actor_role": "admin",
        "action": action,
        "entity_type": "user",
        "entity_id": "u1",
        "reason": None,
        "payload": {},
    }
    return AuditEntry(
        seq=seq,
        at=NOW,
        actor_id="u1",
        actor_role="admin",
        action=action,
        entity_type="user",
        entity_id="u1",
        reason=None,
        payload={},
        prev_hash=prev_hash,
        hash=compute_hash(prev_hash, content),
    )


def _chain(n: int) -> list[AuditEntry]:
    entries: list[AuditEntry] = []
    prev = GENESIS_HASH
    for seq in range(1, n + 1):
        e = _entry(seq, prev)
        entries.append(e)
        prev = e.hash
    return entries


def test_canonical_json_is_deterministic_regardless_of_key_order() -> None:
    a = canonical_json({"b": 1, "a": 2})
    b = canonical_json({"a": 2, "b": 1})
    assert a == b


def test_a_valid_chain_verifies_ok() -> None:
    report = verify_chain(_chain(3))
    assert report.ok is True
    assert report.first_bad_seq is None


def test_empty_chain_verifies_ok_at_genesis() -> None:
    report = verify_chain([])
    assert report.ok is True
    assert report.head_hash == GENESIS_HASH


def test_a_modified_payload_is_detected() -> None:
    entries = _chain(3)
    entries[1] = replace(entries[1], payload={"tampered": True})
    report = verify_chain(entries)
    assert report.ok is False
    assert report.first_bad_seq == 2


def test_a_deleted_entry_is_detected() -> None:
    entries = _chain(3)
    del entries[1]  # seq 2 missing; seq 3's prev_hash no longer matches seq 1's hash
    report = verify_chain(entries)
    assert report.ok is False
    assert report.first_bad_seq == 3


def test_a_reordered_chain_is_detected() -> None:
    entries = _chain(3)
    entries[0], entries[1] = entries[1], entries[0]
    report = verify_chain(entries)
    assert report.ok is False
    assert report.first_bad_seq == entries[0].seq


def test_entry_content_excludes_prev_hash_and_hash() -> None:
    e = _entry(1, GENESIS_HASH)
    content = entry_content(e)
    assert "prev_hash" not in content
    assert "hash" not in content
