"""new_id() -> str: a sortable ULID, no arguments, no state (DOC 3 Shared Kernel, LC-2)."""

from __future__ import annotations

from ulid import ULID


def new_id() -> str:
    """A new, lexicographically sortable ULID string. ULID embeds its own creation time
    internally (python-ulid's concern, not ours); this function never reads the wall clock
    itself, so the ruff ban on `time.time` / `datetime.now` still holds everywhere else."""
    return str(ULID())
