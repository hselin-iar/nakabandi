"""bundle.py — EvidenceBundle (DOC 3 S2). Pure: assembles already-fetched pieces into one JSON-safe
structure; service.py does the fetching (SRP: bundle assembles, hashing hashes, certificate
models, pdf renders, service orchestrates)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    alert_id: str
    generated_at: str
    summary: dict[str, Any] = field(default_factory=dict)
    prediction: dict[str, Any] | None = None
    interception: list[dict[str, Any]] = field(default_factory=list)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    outcomes: list[dict[str, Any]] = field(default_factory=list)
    audit_excerpt: list[dict[str, Any]] = field(default_factory=list)
    audit_head_hash: str = ""
    case_accounts: list[dict[str, Any]] = field(default_factory=list)
    """Account refs already masked for the building principal (DOC 3 S2 testing plan: "bundle
    contains no unmasked refs for non-LEA roles")."""

    def canonical_json(self) -> bytes:
        """Deterministic bytes for hashing and PDF rendering: sorted keys, no whitespace."""
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
