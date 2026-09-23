"""rng_for — deterministic per-name RNG (DOC 3 M1).

rng_for(seed, *names) -> np.random.Generator

Uses SHA-256 of the full (seed, *names) path so that:
  - Same args always give the same generator.
  - Different args always give different generators (collision-resistant).
  - Order matters: rng_for(42, "a", "b") != rng_for(42, "b", "a").
  - Independent subsystems (different name paths) never cross-contaminate.
"""

from __future__ import annotations

import hashlib

import numpy as np


def rng_for(seed: int, *names: str) -> np.random.Generator:
    """Return a reproducible Generator for the given seed + name path.

    Order of names matters: rng_for(42, "a", "b") != rng_for(42, "b", "a").
    Different subsystems using different paths are fully independent.

    Examples
    --------
    >>> gen = rng_for(42, "clusters", "C-0001", "timing")
    >>> gen.integers(0, 100)  # always the same value for this path
    """
    # Build a canonical string that encodes seed + ordered name path.
    # Position prefix (i=name) ensures order always matters.
    path = f"seed={seed}|" + "|".join(f"{i}={n}" for i, n in enumerate(names))
    digest = hashlib.sha256(path.encode("utf-8")).digest()
    # Convert 32-byte digest to a large integer for SeedSequence
    int_seed = int.from_bytes(digest, "big")
    return np.random.default_rng(np.random.SeedSequence(int_seed))
