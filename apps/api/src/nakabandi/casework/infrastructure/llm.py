"""llm.py — NVIDIA NIM (OpenAI-compatible chat completions) client for the case explanation.

The only outbound-network code in casework. It is optional and best-effort: the caller treats any
failure as "no explanation" and shows the deterministic brief. Facts only, never account
references (see domain/explain.build_facts).
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

_THINK_BLOCK = re.compile(r"<think>.*?(</think>|$)", re.DOTALL | re.IGNORECASE)


class NimExplainer:
    def __init__(self, api_key: str, model: str, base_url: str, timeout_s: float = 30.0) -> None:
        self._api_key = api_key
        self.model = model
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._timeout = timeout_s

    def _post(self, payload: dict[str, Any]) -> httpx.Response:
        return httpx.post(
            self._url,
            headers={"Authorization": f"Bearer {self._api_key}", "Accept": "application/json"},
            json=payload,
            timeout=self._timeout,
        )

    def explain(self, system_prompt: str, facts: dict[str, Any]) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(facts, sort_keys=True)},
            ],
            "temperature": 0.2,
            "max_tokens": 700,
            "stream": False,
            # Reasoning models (e.g. Nemotron) otherwise spend the token budget thinking out loud
            # and can return their planning as the answer.
            "chat_template_kwargs": {"enable_thinking": False},
        }
        response = self._post(payload)
        if response.status_code in (400, 422):  # a model that does not know the extra field
            payload.pop("chat_template_kwargs")
            response = self._post(payload)
        response.raise_for_status()
        content = str(response.json()["choices"][0]["message"].get("content") or "")
        return _THINK_BLOCK.sub("", content).strip()
