"""kill -9 and restart (DOC 4 A11 Done When: "after kill -9 and restart, timers and outbox
resume"; DOC 2 §2.7: "crash recovery replays outbox and unprocessed complaints").

Real processes: the API runs as a uvicorn subprocess, is killed with SIGKILL (no shutdown hooks,
no cleanup) in the middle of a burst of ingest requests, and is started again on the same
database. Nothing is simulated except the bank, which is a small local receiver that is DOWN
while the first process runs and UP for the second."""

from __future__ import annotations

import json
import os
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import httpx
from integration.test_live_chain import complaint, hops, registry
from nakabandi.alerting.domain.signing import verify

SERVICE_KEY = "recovery-service-key"
WEBHOOK_SECRET = "recovery-webhook-secret"
REPO = Path(__file__).resolve().parents[4]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Bank(BaseHTTPRequestHandler):
    """Verifies LC-6 signatures like the real bank does; remembers what it accepted."""

    accepted: list[dict] = []

    def do_POST(self) -> None:  # noqa: N802
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        ok = verify(
            WEBHOOK_SECRET,
            self.headers["X-Nakabandi-Timestamp"],
            raw,
            self.headers["X-Nakabandi-Signature"],
        )
        if ok:
            self.accepted.append(json.loads(raw))
        self.send_response(200 if ok else 401)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


class Api:
    def __init__(self, db: Path, bank_url: str) -> None:
        self.port = free_port()
        self.base = f"http://127.0.0.1:{self.port}/api/v1"
        self.env = {
            **os.environ,
            "API_SERVICE_KEY": SERVICE_KEY,
            "JWT_SECRET": "recovery-jwt-secret-at-least-32-bytes-long",
            "DATABASE_URL": f"sqlite:///{db}",
            "WEBHOOK_SECRET": WEBHOOK_SECRET,
            "NAKABANDI_BANK_WEBHOOK_URL": bank_url,
            # the test suite disables the background workers; a real process runs them
            "NAKABANDI_OUTBOX_WORKER_ENABLED": "true",
            "NAKABANDI_TIMER_WORKER_ENABLED": "true",
            # Isolated, guaranteed-empty model store — see integration/conftest.py's client
            # fixture for why: this test asserts an alert gets raised, which needs the
            # fallback heuristic scorer, not whatever real model happens to be on disk.
            "NAKABANDI_MODEL_STORE_DIR": str(db.parent / "models"),
        }
        self.proc: subprocess.Popen | None = None

    def start(self) -> None:
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "nakabandi.main:app", "--port", str(self.port)],
            cwd=REPO,
            env=self.env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                if httpx.get(f"{self.base}/system/health", timeout=2).status_code == 200:
                    return
            except httpx.HTTPError:
                time.sleep(0.3)
        raise AssertionError("the API did not become healthy")

    def kill9(self) -> None:
        assert self.proc is not None
        self.proc.kill()
        self.proc.wait(timeout=10)

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(timeout=10)

    def post(self, path: str, body: dict, timeout: float = 30) -> httpx.Response:
        return httpx.post(
            f"{self.base}/ingest/{path}",
            json=body,
            headers={"X-Nakabandi-Service-Key": SERVICE_KEY},
            timeout=timeout,
        )

    def login(self, role: str) -> httpx.Client:
        client = httpx.Client(base_url=self.base, timeout=30)
        users = client.get("/auth/demo-users").json()
        user = next(u for u in users if u["role"] == role)
        r = client.post(
            "/auth/login", json={"username": user["username"], "password": user["password"]}
        )
        assert r.status_code == 200, r.text
        return client


def query(db: Path, sql: str, *params: object) -> list[tuple]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def wait_for(predicate, seconds: float = 40.0, every: float = 0.5):  # noqa: ANN001, ANN201
    deadline = time.monotonic() + seconds
    last = None
    while time.monotonic() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(every)
    raise AssertionError(f"condition not met within {seconds}s (last: {last!r})")


def test_after_kill_9_and_restart_nothing_is_lost_and_the_outbox_and_timers_resume(
    tmp_path: Path,
) -> None:
    db = tmp_path / "recovery.db"
    Bank.accepted = []
    bank_port = free_port()  # nobody is listening on it yet: the bank is DOWN
    api = Api(db, f"http://127.0.0.1:{bank_port}/webhooks/nakabandi")
    bank: HTTPServer | None = None
    try:
        # ---- first life: a world, an alert, a hold request the DOWN bank cannot receive ----
        api.start()
        assert api.post("registry", registry()).status_code == 200
        assert api.post("complaints", complaint("c1", "a1", 10)).status_code == 200
        assert api.post("hops", hops("c1", "a1", "a2", 15, "h-c1")).status_code == 200
        analyst = api.login("i4c_analyst")
        (alert,) = analyst.get("/alerts", params={"view": "all"}).json()["items"]
        assert alert["status"] == "open"
        account_id = query(db, "SELECT id FROM accounts WHERE account_ref = 'A2'")[0][0]
        hold = analyst.post(
            f"/alerts/{alert['id']}/actions",
            json={
                "type": "request_hold",
                "params": {"account_id": account_id, "proposed_paise": 1_500_000},
            },
        )
        assert hold.status_code == 201, hold.text
        wait_for(  # the worker tries and fails against the down bank: the row exists, unsent
            lambda: query(db, "SELECT COUNT(*) FROM deliveries WHERE status = 'failed'")[0][0] >= 1
        )
        assert query(db, "SELECT COUNT(*) FROM deliveries WHERE status = 'sent'")[0][0] == 0

        # ---- a burst of ingest requests, and SIGKILL in the middle of it ----
        acked: list[str] = []
        lock = threading.Lock()

        def send(n: int) -> None:
            ref = f"burst-{n}"
            body = complaint(ref, f"burst-acct-{n}", 100 + n)
            try:
                r = api.post("complaints", body, timeout=20)
            except httpx.HTTPError:
                return  # the process died under this request: it never acknowledged
            if r.status_code == 200 and r.json()["accepted"] == 1:
                with lock:
                    acked.append(ref)

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(send, n) for n in range(80)]
            wait_for(lambda: len(acked) >= 15, seconds=60)  # let it get going ...
            api.kill9()  # ... then pull the plug: no shutdown hooks, no cleanup
            for f in futures:
                f.result()
        assert 15 <= len(acked) < 80, "the kill must land while the burst is still running"

        # ---- second life: same database, the bank is UP now ----
        bank = HTTPServer(("127.0.0.1", bank_port), Bank)
        threading.Thread(target=bank.serve_forever, daemon=True).start()
        api.start()

        # nothing acknowledged was lost, and nothing is half-done
        stored = {
            r[0]: r[1]
            for r in query(
                db,
                "SELECT external_ref, processing_status FROM complaints "
                "WHERE external_ref LIKE 'burst-%'",
            )
        }
        missing = [ref for ref in acked if ref not in stored]
        assert missing == [], f"acknowledged complaints lost by the crash: {missing}"
        forecasts = {
            r[0]
            for r in query(
                db,
                "SELECT c.external_ref FROM forecasts f JOIN complaints c ON c.id = f.complaint_id",
            )
        }
        for ref, status in stored.items():
            # a stored complaint went through the whole chain in ONE transaction: never a
            # complaint without its forecast, never one left half-processed
            assert status == "processed" and ref in forecasts, (ref, status)
        assert (
            query(db, "SELECT COUNT(*) FROM complaints WHERE processing_status != 'processed'")[0][
                0
            ]
            == 0
        )
        dups = query(
            db,
            "SELECT dedup_key, COUNT(*) FROM alerts "
            "WHERE status IN ('open','escalated','acknowledged') GROUP BY 1 HAVING COUNT(*) > 1",
        )
        assert dups == []

        # the OUTBOX resumed: the hold request the down bank could not take is delivered now
        wait_for(lambda: any(m["kind"] == "hold_request" for m in Bank.accepted), seconds=60)
        (sent,) = [m for m in Bank.accepted if m["kind"] == "hold_request"]
        assert sent["request_id"] == hold.json()["id"]  # the same request, not a new one
        assert query(db, "SELECT status FROM deliveries WHERE webhook_kind = 'hold_request'") == [
            ("sent",)
        ]

        # the sim CLOCK was restored from the database, not reset to 1970
        admin = api.login("admin")
        heat = admin.get("/analytics/heatmap", params={"level": "location"}).json()
        assert datetime.fromisoformat(heat["generated_at"]).year == 2026

        # the TIMERS resumed: an alert nobody attended to, open at the crash, escalates once
        # enough sim time passes. (The hold's alert is ACTIONED and must NOT escalate or expire.)
        open_alerts = query(
            db, "SELECT id, created_at FROM alerts WHERE status = 'open' ORDER BY created_at DESC"
        )
        assert open_alerts, "the burst should have left unattended alerts open"
        unattended_id, created = open_alerts[0]
        created_at = datetime.fromisoformat(created).replace(tzinfo=UTC)
        tick_to = created_at + timedelta(minutes=45)  # past escalate_after_min (30), before expiry
        assert api.post("tick", {"sim_time": tick_to.isoformat()}).status_code == 200
        wait_for(
            lambda: (
                query(db, "SELECT status FROM alerts WHERE id = ?", unattended_id)
                == [("escalated",)]
            ),
            seconds=40,
        )
        assert query(db, "SELECT status FROM alerts WHERE id = ?", alert["id"]) == [("actioned",)]
    finally:
        api.stop()
        if bank is not None:
            bank.shutdown()
            bank.server_close()
