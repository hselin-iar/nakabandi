"""oracle_client.py — HTTP client for the world-sim Oracle API (DOC 3 B7).

ISOLATION RULE: Only this module (in evaluation/) may talk to the oracle.
main.py MUST NOT import evaluation. import-linter enforces both.

The oracle runs on localhost (never routed through Caddy) and exposes:
  GET /oracle/cashouts?from_=<iso>&to=<iso>
  GET /oracle/clusters
  GET /oracle/complaints/{external_ref}/truth
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TruthCashout:
    """Ground-truth cash-out event from the oracle."""

    external_ref: str  # complaint the withdrawal is linked to
    location_id: str  # ATM / branch / VPA id
    cluster_id: str  # mule cluster
    event_at: datetime  # when (sim time)
    amount_paise: int
    channel: str


@dataclass(frozen=True)
class TruthCluster:
    """Ground-truth mule cluster from the oracle."""

    cluster_id: str
    member_account_ids: list[str]
    location_ids: list[str]


@dataclass(frozen=True)
class TruthComplaint:
    """Ground-truth for one complaint."""

    external_ref: str
    cluster_id: str | None  # None if the complaint is innocent noise
    cashout_location_ids: list[str]  # locations where cash was actually taken out
    cashout_event_at: datetime | None


class OracleClient:
    """Thin HTTP client for the world-sim Oracle API.

    All methods are synchronous (evaluation runs offline, no async needed).
    Raises httpx.HTTPStatusError on 4xx / 5xx.
    """

    def __init__(self, base_url: str = "http://localhost:8001", timeout: float = 30.0) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    def cashouts_in_range(self, from_dt: datetime, to_dt: datetime) -> list[TruthCashout]:
        """Return all ground-truth cash-out events in [from_dt, to_dt]."""
        url = f"{self._base}/oracle/cashouts"
        resp = httpx.get(
            url,
            params={"from_": from_dt.isoformat(), "to": to_dt.isoformat()},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        result = []
        for row in data:
            result.append(
                TruthCashout(
                    external_ref=row["external_ref"],
                    location_id=row["location_id"],
                    cluster_id=row["cluster_id"],
                    event_at=datetime.fromisoformat(row["event_at"]),
                    amount_paise=int(row["amount_paise"]),
                    channel=row["channel"],
                )
            )
        return result

    def clusters(self) -> list[TruthCluster]:
        """Return all ground-truth clusters for the current run."""
        resp = httpx.get(f"{self._base}/oracle/clusters", timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json()
        return [
            TruthCluster(
                cluster_id=row["cluster_id"],
                member_account_ids=row.get("member_account_ids", []),
                location_ids=row.get("location_ids", []),
            )
            for row in data
        ]

    def complaint_truth(self, external_ref: str) -> TruthComplaint | None:
        """Return ground-truth for one complaint, or None if not found."""
        url = f"{self._base}/oracle/complaints/{external_ref}/truth"
        resp = httpx.get(url, timeout=self._timeout)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        row = resp.json()
        cashout_at = row.get("cashout_event_at")
        return TruthComplaint(
            external_ref=external_ref,
            cluster_id=row.get("cluster_id"),
            cashout_location_ids=row.get("cashout_location_ids", []),
            cashout_event_at=datetime.fromisoformat(cashout_at) if cashout_at else None,
        )
