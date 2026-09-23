"""Public facade of the pipeline module: what other modules may import (DOC 3).

INVARIANT (DOC 2 §2.1, AGENTS.md Agentic Coding Rules):
  Only `pipeline` and `main.py` call several module facades in sequence.
  No other module imports `pipeline`.
"""

from nakabandi.pipeline.process_complaint import (
    ProcessComplaint,
    ProcessResult,
    RefreshOpenAlerts,
    RetryUnprocessed,
)

__all__ = [
    "ProcessComplaint",
    "ProcessResult",
    "RefreshOpenAlerts",
    "RetryUnprocessed",
]
