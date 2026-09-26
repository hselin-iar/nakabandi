"""Plain-language case explanation: anonymised facts, ethics guard, graceful degradation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from nakabandi.casework.application.explain import ExplainCase
from nakabandi.casework.domain.case import (
    AccountRef,
    Case,
    ClusterEdge,
    ClusterGraph,
    ClusterNode,
    LocationHit,
)
from nakabandi.casework.domain.explain import DISCLAIMER, build_facts, violates_policy

T0 = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)


def _case() -> Case:
    return Case(
        id="case-1",
        cluster_ref="clu-1",
        complaint_count=3,
        victim_count=3,
        total_paise=1_500_000,
        first_seen=T0,
        last_seen=T0 + timedelta(hours=5),
        accounts=[
            AccountRef("a1", "SECRET-ACC-0001", "BNK-1", 2),
            AccountRef("a2", "SECRET-ACC-0002", "BNK-2", 1),
        ],
        top_locations=[LocationHit("LOC-1", 4, T0)],
    )


def _graph() -> ClusterGraph:
    nodes = [
        ClusterNode("a1", "account", "SECRET-ACC-0001", "BNK-1"),
        ClusterNode("a2", "account", "SECRET-ACC-0002", "BNK-2"),
    ]
    edges = [
        ClusterEdge("a1", "a2", 100_000, 1, T0),
        ClusterEdge("a2", "a1", 90_000, 2, T0),
        ClusterEdge("a1", "a1", 50_000, 3, T0),
    ]
    return ClusterGraph("clu-1", 2, "active", 0.0, nodes, edges)


class _Fake:
    model = "fake-model"

    def __init__(self, text: str | Exception) -> None:
        self.text = text
        self.calls = 0

    def explain(self, system_prompt: str, facts: dict) -> str:
        self.calls += 1
        if isinstance(self.text, Exception):
            raise self.text
        return self.text


GOOD = (
    "Three complaints reached a small network of two accounts across two banks. "
    "The pattern is consistent with money moving back and forth before cash-out at one location."
)


def test_facts_never_carry_account_references() -> None:
    facts = str(build_facts(_case(), _graph()))
    assert "SECRET" not in facts
    assert "a1" not in facts.replace("'a1'", "")  # no raw ids either
    assert "Account A" in facts


def test_facts_describe_the_trail() -> None:
    trail = build_facts(_case(), _graph())["trail"]
    assert trail["routes_where_money_flows_both_ways"] == 1
    assert trail["transfers_back_to_the_same_account"] == 1
    assert trail["deepest_hop"] == 3


def test_guard_rejects_guilt_language_and_empty_text() -> None:
    assert violates_policy("These criminals ran a large scam network across many banks today.")
    assert violates_policy("short")
    assert not violates_policy(GOOD)


def test_guard_rejects_leaked_reasoning_and_overlong_text() -> None:
    leak = "We need to produce 3 short paragraphs, max 150 words total, using only the JSON facts."
    assert violates_policy(leak)
    assert violates_policy("Okay, the user wants a summary of this network of accounts and banks.")
    assert violates_policy("word " * 300)


def test_not_configured_is_unavailable_without_a_call() -> None:
    result = ExplainCase(None).run(_case(), _graph())
    assert (result.available, result.reason) == (False, "not_configured")


def test_good_text_gets_the_fir_disclaimer_and_is_cached() -> None:
    fake = _Fake(GOOD)
    uc = ExplainCase(fake)
    first = uc.run(_case(), _graph())
    second = uc.run(_case(), _graph())
    assert first.available and first.text is not None and first.text.endswith(DISCLAIMER)
    assert second == first
    assert fake.calls == 1


def test_model_error_and_rejected_text_degrade_quietly() -> None:
    assert ExplainCase(_Fake(RuntimeError("boom"))).run(_case(), _graph()).reason == "model_error"
    bad = _Fake("The accused fraudsters are guilty of running this network of mule accounts.")
    assert ExplainCase(bad).run(_case(), _graph()).reason == "rejected"


def test_nim_client_speaks_openai_chat_completions() -> None:
    """The real client against a local stand-in for the NIM endpoint (no network)."""
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from nakabandi.casework.infrastructure.llm import NimExplainer

    seen: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.update(path=self.path, auth=self.headers["Authorization"], body=body)
            payload = json.dumps({"choices": [{"message": {"content": f"  {GOOD}  "}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        client = NimExplainer("k-123", "some/model", f"http://127.0.0.1:{server.server_port}/v1")
        text = client.explain("system", {"a": 1})
    finally:
        server.shutdown()
    assert text == GOOD
    assert seen["path"] == "/v1/chat/completions"
    assert seen["auth"] == "Bearer k-123"
    assert seen["body"]["model"] == "some/model"
    assert seen["body"]["messages"][0] == {"role": "system", "content": "system"}
