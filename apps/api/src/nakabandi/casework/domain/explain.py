"""explain.py — the facts and guard rails for the plain-language cluster explanation.

Pure. `build_facts` reduces a case and its money-trail graph to aggregate, anonymised facts (no
account reference, no account id, no bank account number: accounts are only ever "Account A, B,
C" aliases, banks and locations are public identifiers). `SYSTEM_PROMPT` and `violates_policy`
carry DOC 1 §1.5 into the model call: state facts, never assert guilt, never name a person,
never claim legal compliance. The model's text is only shown if it passes `violates_policy`;
otherwise the caller falls back to the deterministic brief.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from nakabandi.casework.domain.case import Case, ClusterGraph

DISCLAIMER = "Whether to register an FIR is the investigating officer's decision."

SYSTEM_PROMPT = (
    "You write short plain-English explanations of money-mule network patterns for police "
    "officers and bank fraud analysts who are not data scientists.\n"
    "Rules you must follow:\n"
    "- Use ONLY the facts in the JSON the user sends. Do not invent numbers, names, places or "
    "events. Refer to accounts only as 'Account A', 'Account B' and so on.\n"
    "- State what the data shows, in hedged language ('the pattern is consistent with', 'this "
    "may indicate'). Never say or imply that anyone is guilty, a criminal, a fraudster or an "
    "accused person. Never name or describe a real person. Never claim legal compliance or "
    "certainty.\n"
    "- Write 3 short paragraphs, at most 150 words in total, no headings, no bullet lists, no "
    "markdown: (1) what happened and how much money is involved, (2) how the money moved "
    "through the network and where it pooled or left, (3) what an officer could verify next "
    "(for example: which banks to contact, which locations to check, whether more complaints "
    "are linked).\n"
    "- Do not mention FIRs or legal action; that is added separately."
)

_FORBIDDEN = re.compile(
    r"\b(guilty|criminals?|fraudsters?|culprits?|accused|convict\w*|perpetrators?|scammers?|"
    r"thieves|thief|lawful|legally compliant|arrest\w*)\b",
    re.IGNORECASE,
)


# A reasoning model that leaks its planning ("We need to produce 3 paragraphs...") instead of the
# answer: never show that to an officer.
_THINKING_LEAK = re.compile(
    r"^\s*(okay|we need|let'?s|first,? (i|we)|the user|i need to|hmm|alright|so,? (i|we)|note:)",
    re.IGNORECASE,
)
MAX_WORDS = 220


def violates_policy(text: str) -> bool:
    """True when the model text asserts guilt or legal conclusions, leaks its reasoning, or is
    unusably empty or long."""
    stripped = text.strip()
    if len(stripped) < 40 or len(stripped) > 2000 or len(stripped.split()) > MAX_WORDS:
        return True
    if _THINKING_LEAK.search(stripped) or "</think>" in stripped.lower():
        return True
    return _FORBIDDEN.search(stripped) is not None


def _alias(i: int) -> str:
    return f"Account {chr(ord('A') + i)}" if i < 26 else f"Account {i + 1}"


def build_facts(case: Case, graph: ClusterGraph) -> dict[str, Any]:
    """Aggregate, anonymised facts about one cluster, safe to send to an external model."""
    inbound: Counter[str] = Counter()
    outbound: Counter[str] = Counter()
    handled: Counter[str] = Counter()
    pairs: set[tuple[str, str]] = set()
    self_transfers = 0
    total_moved = 0
    for e in graph.edges:
        total_moved += e.amount_paise
        if e.from_id == e.to_id:
            self_transfers += 1
            continue
        pairs.add((e.from_id, e.to_id))
        outbound[e.from_id] += 1
        inbound[e.to_id] += 1
        handled[e.from_id] += e.amount_paise
        handled[e.to_id] += e.amount_paise
    return_flows = sum(1 for a, b in pairs if (b, a) in pairs) // 2
    node_bank = {n.id: n.bank_id for n in graph.nodes}
    hubs = []
    for i, (acc, moved) in enumerate(handled.most_common(3)):
        hubs.append(
            {
                "alias": _alias(i),
                "bank": node_bank.get(acc, "unknown"),
                "transfers_in": inbound[acc],
                "transfers_out": outbound[acc],
                "share_of_money_handled_pct": (
                    round(100 * moved / (2 * total_moved)) if total_moved else 0
                ),
            }
        )
    touched = set(inbound) | set(outbound)
    duration_h = (case.last_seen - case.first_seen).total_seconds() / 3600
    return {
        "cluster": case.cluster_ref,
        "complaints": case.complaint_count,
        "victims": case.victim_count,
        "total_reported_rupees": round(case.total_paise / 100),
        "first_seen": case.first_seen.isoformat(),
        "last_seen": case.last_seen.isoformat(),
        "active_for_hours": round(duration_h, 1),
        "single_complaint_so_far": case.single_complaint,
        "accounts_in_cluster": len(case.accounts),
        "banks_involved": dict(Counter(a.bank_id for a in case.accounts)),
        "trail": {
            "accounts_with_traced_transfers": len(touched),
            "distinct_transfer_routes": len(pairs),
            "traced_transfers": len(graph.edges),
            "money_moved_rupees": round(total_moved / 100),
            "deepest_hop": max((e.layer for e in graph.edges), default=0),
            "accounts_that_only_send": sum(1 for a in touched if inbound[a] == 0),
            "accounts_that_only_receive": sum(1 for a in touched if outbound[a] == 0),
            "routes_where_money_flows_both_ways": return_flows,
            "transfers_back_to_the_same_account": self_transfers,
            "busiest_accounts": hubs,
        },
        "cash_out_locations": [
            {"location": h.location_id, "cash_outs": h.count} for h in case.top_locations[:5]
        ],
    }
