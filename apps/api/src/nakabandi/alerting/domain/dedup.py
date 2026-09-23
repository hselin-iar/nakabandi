"""dedup_key() (DOC 3 M4: "dedup_key(cluster_id, target) -> str")."""

from __future__ import annotations

from nakabandi.shared import Id


def dedup_key(cluster_id: Id, target_kind: str, target_id: Id) -> str:
    """Stable key that identifies a unique (cluster, target) pair.

    An open alert found by this key is merged; if none exists a new alert is created.
    """
    return f"{cluster_id}:{target_kind}:{target_id}"
