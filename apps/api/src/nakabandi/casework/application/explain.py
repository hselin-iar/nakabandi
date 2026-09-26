"""explain.py — ExplainCase: an optional plain-language explanation of one case (DOC 1 §1.5).

Never raises for a model problem: no key, a network error, a slow answer or text that breaks the
ethics guard all come back as `available=False`, and the UI keeps the deterministic brief. Results
are cached per (case, facts) so an unchanged cluster costs one model call, not one per page view.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol

import structlog

from nakabandi.casework.domain.case import Case, ClusterGraph
from nakabandi.casework.domain.explain import (
    DISCLAIMER,
    SYSTEM_PROMPT,
    build_facts,
    violates_policy,
)

logger = structlog.get_logger(__name__)


class Explainer(Protocol):
    model: str

    def explain(self, system_prompt: str, facts: dict[str, Any]) -> str: ...


@dataclass(frozen=True, slots=True)
class Explanation:
    available: bool
    text: str | None
    model: str | None
    reason: str | None = None  # why not available: "not_configured" | "model_error" | "rejected"


class ExplainCase:
    def __init__(self, explainer: Explainer | None, cache_max: int = 256) -> None:
        self._explainer = explainer
        self._cache: dict[str, Explanation] = {}
        self._cache_max = cache_max

    @property
    def configured(self) -> bool:
        return self._explainer is not None

    def run(self, case: Case, graph: ClusterGraph) -> Explanation:
        if self._explainer is None:
            return Explanation(False, None, None, "not_configured")
        facts = build_facts(case, graph)
        key = hashlib.sha256(
            json.dumps([case.id, facts], sort_keys=True, default=str).encode()
        ).hexdigest()
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        try:
            text = self._explainer.explain(SYSTEM_PROMPT, facts)
        except Exception as exc:  # noqa: BLE001 - any model/network failure degrades to the brief
            logger.warning("casework.explain.model_error", error=type(exc).__name__)
            return Explanation(False, None, self._explainer.model, "model_error")
        if violates_policy(text):
            logger.warning("casework.explain.rejected", case_id=case.id)
            result = Explanation(False, None, self._explainer.model, "rejected")
        else:
            result = Explanation(True, f"{text}\n\n{DISCLAIMER}", self._explainer.model)
        if len(self._cache) >= self._cache_max:
            self._cache.pop(next(iter(self._cache)))
        if result.available:  # failures are retried on the next view
            self._cache[key] = result
        return result
