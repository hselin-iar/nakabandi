"""emitter.py — JsonlEmitter and ApiEmitter (DOC 3 M1, no live loop for B1).

  JsonlEmitter   writes batches as newline-delimited JSON to a file or stdout
  ApiEmitter     POSTs batches to the ingest API with idempotent retry (no live loop in B1)

For B1 only JsonlEmitter is exercised. ApiEmitter is included for the golden test
(Sync 2) but the live runner loop lives in B5.

Error policy (DOC 3 M1):
  - API unreachable / 5xx: retry with backoff, same idempotency key, up to max_retries.
  - API 4xx: log, mark batch as "invalid", stop. A 4xx is a contract bug, not transient.
  - Stall: after max_retries, emitter enters STALLED state; buffers up to buffer_cap batches.
"""

from __future__ import annotations

import sys
import time
from enum import StrEnum
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel


class EmitterState(StrEnum):
    OK = "ok"
    STALLED = "stalled"


class JsonlEmitter:
    """Write Pydantic batch models as JSONL (one JSON object per line)."""

    def __init__(self, path: Path | str | None = None) -> None:
        """
        Args:
            path: Output file path. If None, writes to stdout.
        """
        self._path = Path(path) if path is not None else None
        self._file = None

    def open(self) -> None:
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._file = self._path.open("a", encoding="utf-8")

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None

    def emit(self, batch: BaseModel) -> None:
        """Serialise one batch model as a single JSON line."""
        line = batch.model_dump_json() + "\n"
        if self._file is not None:
            self._file.write(line)
        else:
            sys.stdout.write(line)
            sys.stdout.flush()

    def __enter__(self) -> JsonlEmitter:
        self.open()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


class ApiEmitter:
    """POST batches to the ingest API with idempotent retry.

    No live runner loop in B1; this class is used by the HistoryRunner and by Sync 2 tests.
    """

    def __init__(
        self,
        base_url: str,
        service_key: str,
        max_retries: int = 5,
        backoff_base_s: float = 1.0,
        buffer_cap: int = 200,
        timeout_s: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "X-Service-Key": service_key,
            "Content-Type": "application/json",
        }
        self._max_retries = max_retries
        self._backoff_base = backoff_base_s
        self._buffer_cap = buffer_cap
        self._timeout = timeout_s
        self.state: EmitterState = EmitterState.OK
        self.last_error: str | None = None
        self._buffer: list[tuple[str, str, str]] = []  # (endpoint, idem_key, json_body)

    def emit(self, endpoint: str, batch: BaseModel) -> dict:
        """POST one batch. Returns the response dict on success.

        Uses the model's idempotency_key field for dedup.
        Raises RuntimeError on 4xx (contract violation).
        Enters STALLED after max_retries on 5xx/network errors.
        """
        body = batch.model_dump_json()
        idem_key = getattr(batch, "idempotency_key", "")

        for attempt in range(self._max_retries + 1):
            try:
                resp = httpx.post(
                    f"{self._base_url}{endpoint}",
                    content=body,
                    headers=self._headers,
                    timeout=self._timeout,
                )
                if resp.status_code == 200:
                    self.state = EmitterState.OK
                    self.last_error = None
                    return resp.json()
                if 400 <= resp.status_code < 500:
                    raise RuntimeError(
                        f"ApiEmitter 4xx on {endpoint}: {resp.status_code} {resp.text[:200]}"
                    )
                # 5xx — retry
                self.last_error = f"HTTP {resp.status_code}"
            except httpx.TransportError as exc:
                self.last_error = str(exc)

            if attempt < self._max_retries:
                sleep_s = self._backoff_base * (2**attempt)
                time.sleep(sleep_s)

        # Max retries exceeded
        self.state = EmitterState.STALLED
        if len(self._buffer) < self._buffer_cap:
            self._buffer.append((endpoint, idem_key, body))
        return {}

    def flush_buffer(self) -> int:
        """Attempt to drain the stall buffer. Returns number successfully flushed."""
        if not self._buffer:
            return 0
        flushed = 0
        remaining = []
        for endpoint, _idem, body in self._buffer:
            try:
                resp = httpx.post(
                    f"{self._base_url}{endpoint}",
                    content=body,
                    headers=self._headers,
                    timeout=self._timeout,
                )
                if resp.status_code == 200:
                    flushed += 1
                    continue
            except httpx.TransportError:
                pass
            remaining.append((endpoint, _idem, body))
        self._buffer = remaining
        if not self._buffer:
            self.state = EmitterState.OK
        return flushed
