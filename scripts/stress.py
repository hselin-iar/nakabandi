"""npm run stress: post complaints to a RUNNING API at a fixed rate and check nothing was lost or
duplicated (DOC 4 A11: "50 complaints/s for 60 s: no lost complaints, no duplicate alerts").

    uv run python scripts/stress.py --base-url http://127.0.0.1:8000 --service-key KEY \\
        --db /path/to/nakabandi.db [--rate 50] [--duration 60] [--login admin]

Each complaint is its own request (batch of one) through the real /ingest route, so each one runs
the whole live chain in-request, exactly as in production. Requests are paced to the target rate
and sent concurrently; the report says what rate was actually achieved, because an API that cannot
keep up shows it as a lower achieved rate and higher latency, not as an error.

Checks (need --db, a read-only look at the API's SQLite file; run on the API's machine):
  no lost complaints   every accepted complaint is stored and `processed`
  no duplicates        no two open alerts share a dedup key; one complaint = one row
With --login (admin or demo_operator) it also prints the API's own /system/metrics."""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sqlite3
import statistics
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

BASE = datetime(2026, 2, 1, 0, 0, tzinfo=UTC)


def make_registry(n_locations: int, n_units: int, seed: int) -> dict:
    rng = random.Random(seed)
    locations = [
        {
            "id": f"S-LOC-{i:04d}",
            "kind": ("ATM", "BRANCH", "AGENT")[i % 3],
            "bank_id": "S-BANK",
            "lat": 26.0 + rng.random() * 0.4,
            "lon": 80.0 + rng.random() * 0.4,
            "district_id": "S-D1",
            "cell_id": f"S-CELL-{i % 20}",
            "source": "synthetic",
            "display_name": f"Stress location {i}",
            "area_type": "urban",
            "activity_index": round(rng.random(), 3),
        }
        for i in range(n_locations)
    ]
    return {
        "version": f"stress-{seed}",
        "banks": [{"id": "S-BANK", "name": "Stress Bank", "short_code": "SB"}],
        "regions": [
            {"id": "S-ST", "level": "state", "name": "S", "parent_id": None, "geojson_ref": None},
            {
                "id": "S-D1",
                "level": "district",
                "name": "D",
                "parent_id": "S-ST",
                "geojson_ref": None,
            },
        ],
        "cells": [
            {
                "id": f"S-CELL-{c}",
                "grid_km": 5,
                "row": c,
                "col": c,
                "district_id": "S-D1",
                "centroid_lat": 26.0 + 0.02 * c,
                "centroid_lon": 80.0 + 0.02 * c,
            }
            for c in range(20)
        ],
        "locations": locations,
        "units": [
            {
                "id": f"S-UNIT-{u}",
                "kind": "station",
                "district_id": "S-D1",
                "lat": 26.0 + rng.random() * 0.4,
                "lon": 80.0 + rng.random() * 0.4,
                "status": "active",
            }
            for u in range(n_units)
        ],
    }


def make_complaint(
    n: int, run: str, rng: random.Random, accounts: list[str], n_locations: int
) -> dict:
    at = BASE + timedelta(seconds=n)
    reuse = accounts and rng.random() < 0.3  # a reused mule joins an existing cluster
    account = rng.choice(accounts) if reuse else f"stress-{run}-acct-{n}"
    if not reuse:
        accounts.append(account)
    ref = f"stress-{run}-{n}"
    return {
        "batch_id": ref,
        "idempotency_key": ref,
        "sim_time": at.isoformat(),
        "items": [
            {
                "external_ref": ref,
                "category": rng.choice(["upi_phishing", "digital_arrest", "task_job_scam"]),
                "amount_paise": rng.choice([300_000, 2_000_000, 15_000_000]),
                "victim_district_id": "S-D1",
                "credited_at": (at - timedelta(minutes=5)).isoformat(),
                "reported_event_at": (at - timedelta(minutes=2)).isoformat(),
                "observed_at": at.isoformat(),
                "layer1_account": {
                    "account_ref": account,
                    "bank_id": "S-BANK",
                    "home_location_id": f"S-LOC-{rng.randrange(n_locations):04d}",
                },
            }
        ],
    }


async def run(args: argparse.Namespace) -> dict:
    run_id = f"{int(time.time()) % 100000}"  # noqa: TID251 - a label for this run, not domain time
    rng = random.Random(args.seed)
    headers = {"X-Nakabandi-Service-Key": args.service_key}
    accounts: list[str] = []
    latencies: list[float] = []
    errors: list[str] = []
    accepted = 0

    limits = httpx.Limits(
        max_connections=args.concurrency, max_keepalive_connections=args.concurrency
    )
    async with httpx.AsyncClient(
        base_url=args.base_url, headers=headers, timeout=60, limits=limits
    ) as client:
        r = await client.post(
            "/api/v1/ingest/registry", json=make_registry(args.locations, args.units, args.seed)
        )
        r.raise_for_status()

        total = int(args.rate * args.duration)
        sem = asyncio.Semaphore(args.concurrency)

        async def send(n: int) -> None:
            nonlocal accepted
            body = make_complaint(n, run_id, rng, accounts, args.locations)
            async with sem:
                started = time.perf_counter()
                try:
                    resp = await client.post("/api/v1/ingest/complaints", json=body)
                    latencies.append(time.perf_counter() - started)
                    if resp.status_code != 200:
                        errors.append(f"{resp.status_code} {resp.text[:120]}")
                    else:
                        payload = resp.json()
                        accepted += payload["accepted"]
                        if payload["rejected"]:
                            errors.append(f"rejected {payload['rejected'][:1]}")
                except httpx.HTTPError as exc:
                    errors.append(f"{type(exc).__name__}: {exc}")

        start = time.perf_counter()
        tasks = []
        for n in range(total):  # pace: complaint n is due at n / rate seconds
            due = start + n / args.rate
            delay = due - time.perf_counter()
            if delay > 0:
                await asyncio.sleep(delay)
            tasks.append(asyncio.create_task(send(n)))
        sent_by = time.perf_counter() - start
        await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start

        metrics = None
        if args.login:
            users = (await client.get("/api/v1/auth/demo-users")).json()
            user = next(u for u in users if u["role"] == args.login)
            await client.post(
                "/api/v1/auth/login",
                json={"username": user["username"], "password": user["password"]},
            )
            mr = await client.get("/api/v1/system/metrics")
            metrics = mr.json() if mr.status_code == 200 else {"error": mr.status_code}

    lat_ms = sorted(x * 1000 for x in latencies)

    def pct(p: float) -> float:
        return lat_ms[max(0, int(len(lat_ms) * p) - 1)] if lat_ms else 0.0

    return {
        "sent": total,
        "accepted": accepted,
        "errors": len(errors),
        "error_samples": errors[:3],
        "target_rate": args.rate,
        "paced_for_s": round(sent_by, 2),
        "elapsed_s": round(elapsed, 2),
        "achieved_rate": round(total / elapsed, 2),
        "latency_ms": {
            "p50": round(pct(0.5), 1),
            "p95": round(pct(0.95), 1),
            "p99": round(pct(0.99), 1),
            "max": round(lat_ms[-1], 1) if lat_ms else 0,
            "mean": round(statistics.mean(lat_ms), 1) if lat_ms else 0,
        },
        "run": run_id,
        "metrics": metrics,
    }


def verify(db: Path, run_id: str, accepted: int) -> dict:
    """Read-only checks against the API's own database."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    like = f"stress-{run_id}-%"
    stored = con.execute(
        "SELECT COUNT(*) FROM complaints WHERE external_ref LIKE ?", (like,)
    ).fetchone()[0]
    by_status = dict(
        con.execute(
            "SELECT processing_status, COUNT(*) FROM complaints "
            "WHERE external_ref LIKE ? GROUP BY 1",
            (like,),
        ).fetchall()
    )
    dup_refs = con.execute(
        "SELECT COUNT(*) FROM (SELECT external_ref FROM complaints WHERE external_ref LIKE ? "
        "GROUP BY 1 HAVING COUNT(*) > 1)",
        (like,),
    ).fetchone()[0]
    dup_alerts = con.execute(
        "SELECT dedup_key, COUNT(*) FROM alerts "
        "WHERE status IN ('open','escalated','acknowledged') "
        "GROUP BY 1 HAVING COUNT(*) > 1"
    ).fetchall()
    alerts = con.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    forecasts = con.execute("SELECT COUNT(*) FROM forecasts").fetchone()[0]
    con.close()
    return {
        "complaints_stored": stored,
        "complaints_by_status": by_status,
        "lost": accepted - stored,
        "duplicate_complaint_refs": dup_refs,
        "duplicate_open_alerts": len(dup_alerts),
        "alerts": alerts,
        "forecasts": forecasts,
        "PASS": stored == accepted
        and dup_refs == 0
        and not dup_alerts
        and by_status.get("processed", 0) == stored,
    }


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--service-key", required=True)
    p.add_argument("--db", type=Path, help="the API's SQLite file, for the lost/duplicate checks")
    p.add_argument("--rate", type=float, default=50.0, help="complaints per second (default 50)")
    p.add_argument("--duration", type=float, default=60.0, help="seconds (default 60)")
    p.add_argument("--concurrency", type=int, default=64)
    p.add_argument("--locations", type=int, default=200)
    p.add_argument("--units", type=int, default=20)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--login", choices=["admin", "demo_operator"], help="also print /system/metrics")
    args = p.parse_args(argv)

    result = asyncio.run(run(args))
    if args.db:
        result["verify"] = verify(args.db, result["run"], result["accepted"])
    print(json.dumps(result, indent=2))
    ok = result["errors"] == 0 and result.get("verify", {}).get("PASS", True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
