"""hashing.py — hash_report(components) -> HashReport (DOC 3 S2). Pure and reproducible: same
input bytes always give the same output (sorted by component name before hashing)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class HashedItem:
    name: str
    sha256: str


@dataclass(frozen=True, slots=True)
class HashReport:
    algorithm: str
    items: list[HashedItem] = field(default_factory=list)
    bundle_sha256: str = ""


def hash_report(components: dict[str, bytes]) -> HashReport:
    items = [
        HashedItem(name=name, sha256=hashlib.sha256(data).hexdigest())
        for name, data in sorted(components.items())
    ]
    canonical = "".join(f"{i.name}:{i.sha256}\n" for i in items).encode("utf-8")
    bundle_sha256 = hashlib.sha256(canonical).hexdigest()
    return HashReport(algorithm="SHA-256", items=items, bundle_sha256=bundle_sha256)
