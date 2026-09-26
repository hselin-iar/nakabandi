"""Prime the local demo stack so it opens with LIVE alerts.

Why it is needed: an alert's window is 75 simulated minutes, and the API clock is the simulation
clock, so any alert raised earlier than "now" is already expired and a fresh stack (or one whose
simulator has stopped) shows only closed alerts.

What it does, through the real ingest API only (nothing is written to the database directly):
  1. reads the current simulation time from the API's own stream;
  2. reports fresh complaints from new mule accounts whose home facility is a real branch/ATM, one
     per district across the demo states, spread over the next ~30 simulated minutes with varied
     amounts, so each forecast has one confident place to point at and severities differ;
  3. acknowledges a few of the resulting alerts as an analyst, so the inbox shows a mix of states;
  4. `--tick` keeps the simulation clock running in real time (1x) so countdowns tick and alerts
     stay open for their full 75 minutes.

Usage (stack from infra/docker-compose.yml running on localhost:8001):
    uv run python scripts/demo_prime.py            # raise the alerts
    uv run python scripts/demo_prime.py --tick     # keep the clock running (leave it open)

Everything here is synthetic demo data.
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

API = "http://localhost:8001/api/v1"
CONTAINER = "infra-api-1"
ANALYST = ("Aarav Kulkarni", "demo-i4c-2026")
CATEGORIES = ["upi_phishing", "digital_arrest", "investment_scam"]


def service_key() -> str:
    out = subprocess.run(
        ["docker", "exec", CONTAINER, "printenv", "API_SERVICE_KEY"],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def login() -> httpx.Client:
    client = httpx.Client(base_url=API, timeout=30)
    r = client.post("/auth/login", json={"username": ANALYST[0], "password": ANALYST[1]})
    r.raise_for_status()
    return client


def sim_now(client: httpx.Client) -> datetime:
    with client.stream("GET", "/stream", timeout=10) as r:
        for line in r.iter_lines():
            if line.startswith("data:") and "sim_time" in line:
                return datetime.fromisoformat(json.loads(line[5:])["sim_time"])
    raise RuntimeError("no sim.time event on /stream")


def snapshot_db() -> Path:
    tmp = Path(tempfile.mkdtemp()) / "snap.db"
    subprocess.run(
        [
            "docker",
            "exec",
            CONTAINER,
            "python",
            "-c",
            "import sqlite3;s=sqlite3.connect('/data/nakabandi.db');"
            "d=sqlite3.connect('/tmp/demo_snap.db');s.backup(d);d.close()",
        ],
        check=True,
    )
    subprocess.run(["docker", "cp", f"{CONTAINER}:/tmp/demo_snap.db", str(tmp)], check=True)
    return tmp


def candidate_locations(
    db: Path, wanted: int, rng: random.Random
) -> list[tuple[str, str, str, str]]:
    """One real facility per district, spread over the states.

    Returns (location_id, bank_id, district_id, name) tuples.

    A brand-new mule account whose home facility is known gives the forecast one confident place
    to point at (a cold cluster's only evidence is its home), which is what raises an alert;
    long-running clusters cash out over dozens of places and rightly abstain.
    """
    con = sqlite3.connect(db)
    all_rows = con.execute(
        "SELECT id, bank_id, district_id, display_name, kind FROM locations ORDER BY id"
    ).fetchall()
    con.close()
    rows = [r[:4] for r in all_rows if r[4] in ("BRANCH", "ATM")]
    # The forecast spreads probability over every facility of the complaint's bank in the victim's
    # district, so a facility is only "confident" when that bank has one or two of them there.
    per_group: dict[tuple[str, str], int] = {}
    for loc in all_rows:  # every kind counts: agents are candidates too
        per_group[(loc[1], loc[2])] = per_group.get((loc[1], loc[2]), 0) + 1
    by_state: dict[str, dict[str, list[tuple[str, str, str, str]]]] = {}
    for loc in rows:
        if per_group[(loc[1], loc[2])] > 2:
            continue
        state = loc[2].split("-")[0]
        by_state.setdefault(state, {}).setdefault(loc[2], []).append(loc)
    picked: list[tuple[str, str, str, str]] = []
    states = sorted(by_state)
    while len(picked) < wanted and any(by_state.values()):
        for st in states:
            if not by_state[st] or len(picked) >= wanted:
                continue
            district = rng.choice(sorted(by_state[st]))
            picked.append(rng.choice(by_state[st].pop(district)))
    return picked


def raise_alerts(count: int) -> None:
    key = service_key()
    client = login()
    now = sim_now(client)
    rng = random.Random(now.isoformat())
    accounts = candidate_locations(snapshot_db(), count, rng)
    if not accounts:
        sys.exit("no facilities found - is the registry loaded?")
    stamp = now.strftime("%m%d%H%M%S")
    headers = {"X-Service-Key": key}
    raised = 0
    for i, (loc_id, bank, district, loc_name) in enumerate(accounts):
        # spread over the last 30 simulated minutes, oldest first, all after the current clock
        observed = now + timedelta(minutes=2 + i * 28 / max(1, len(accounts) - 1))
        credited = observed - timedelta(minutes=rng.randint(9, 16))
        reported = observed - timedelta(minutes=rng.randint(3, 6))
        big = i % 4 == 0
        amount_rupees = (
            rng.randint(2_500_000, 4_500_000) if big else rng.randint(150_000, 1_800_000)
        )
        batch = {
            "batch_id": f"demo-{stamp}-{i}",
            "idempotency_key": f"demo-{stamp}-{i}",
            "sim_time": observed.isoformat(),
            "items": [
                {
                    "external_ref": f"DEMO-{stamp}-{i:02d}",
                    "category": CATEGORIES[i % len(CATEGORIES)],
                    "amount_paise": amount_rupees * 100,
                    "victim_district_id": district,
                    "credited_at": credited.isoformat(),
                    "reported_event_at": reported.isoformat(),
                    "observed_at": observed.isoformat(),
                    "layer1_account": {
                        "account_ref": f"MULE-{stamp}-{i:02d}",
                        "bank_id": bank,
                        "home_location_id": loc_id,
                    },
                }
            ],
        }
        r = httpx.post(f"{API}/ingest/complaints", json=batch, headers=headers, timeout=60)
        ok = r.status_code == 200 and not r.json().get("rejected")
        raised += int(ok)
        print(
            f"  complaint {i + 1:>2}/{len(accounts)}  {loc_name[:30]:<30} {district:<7}"
            f" ₹{amount_rupees:>9,}  ->",
            "ok" if ok else r.text[:120],
        )
        time.sleep(0.4)
    time.sleep(3)

    alerts = client.get("/alerts", params={"view": "queue"}).json()["items"]
    live = [a for a in alerts if a["status"] == "open"]
    print(f"\n{raised} complaints ingested; {len(live)} open alerts now")
    for a in sorted(live, key=lambda x: x["severity"])[:3]:
        client.post(
            f"/alerts/{a['id']}/actions",
            json={"type": "acknowledge", "reason": "Demo: picked up by analyst", "params": {}},
        )
    print("acknowledged a few so the inbox shows a mix of states")


def tick_forever(step_s: float) -> None:
    """Advance the simulation clock in real time (1x)."""
    key = service_key()
    client = login()
    t = sim_now(client)
    print(f"ticking from {t.isoformat()} - Ctrl-C to stop")
    n = 0
    while True:
        time.sleep(step_s)
        t += timedelta(seconds=step_s)
        n += 1
        httpx.post(
            f"{API}/ingest/tick",
            json={"sim_time": t.astimezone(UTC).isoformat()},
            headers={"X-Service-Key": key},
            timeout=30,
        )
        if n % 60 == 0:
            print("  sim time", t.isoformat())


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--tick", action="store_true", help="keep the simulation clock running at 1x")
    ap.add_argument("--step", type=float, default=5.0, help="seconds per tick (default 5)")
    ap.add_argument("--alerts", type=int, default=14, help="how many fresh complaints to raise")
    args = ap.parse_args()
    tick_forever(args.step) if args.tick else raise_alerts(args.alerts)
