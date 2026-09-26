"""llm.py — NVIDIA NIM (OpenAI-compatible chat completions) client for the case explanation.

The only outbound-network code in casework. It is optional and best-effort: the caller treats any
failure as "no explanation" and shows the deterministic brief. Facts only, never account
references (see domain/explain.build_facts).
"""

from __future__ import annotations

import json
from typing import Any

import httpx


class NimExplainer:
    def __init__(self, api_key: str, model: str, base_url: str, timeout_s: float = 30.0) -> None:
        self._api_key = api_key
        self.model = model
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._timeout = timeout_s

    def explain(self, system_prompt: str, facts: dict[str, Any]) -> str:
        response = httpx.post(
            self._url,
            headers={"Authorization": f"Bearer {self._api_key}", "Accept": "application/json"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(facts, sort_keys=True)},
                ],
                "temperature": 0.2,
                "max_tokens": 400,
                "stream": False,
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        return str(response.json()["choices"][0]["message"]["content"]).strip()
