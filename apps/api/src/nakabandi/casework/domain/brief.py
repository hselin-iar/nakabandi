"""brief.py — render_brief (DOC 3 S1). Pure formatting: states facts, never asserts guilt or
names real persons (DOC 1 §1.5), and never prints an account ref or account id — only aggregate
counts and location/bank identifiers — so the brief is safe for every role without per-principal
masking logic living in the domain layer.
"""

from __future__ import annotations

from pathlib import Path
from string import Template

from nakabandi.casework.domain.case import Case

_TEMPLATES = Path(__file__).resolve().parent.parent / "infrastructure" / "templates"

_DISCLAIMER = "Whether to register an FIR is the investigating officer's decision."


def render_brief(case: Case, locale: str = "en") -> str:
    path = _TEMPLATES / locale / "case_brief.md"
    if not path.exists():
        path = _TEMPLATES / "en" / "case_brief.md"
    banks = sorted({a.bank_id for a in case.accounts})
    locations = sorted({loc.location_id for loc in case.top_locations})
    template = Template(path.read_text(encoding="utf-8"))
    return template.substitute(
        cluster_ref=case.cluster_ref,
        complaint_count=str(case.complaint_count),
        victim_count=str(case.victim_count),
        total_rupees=f"{case.total_paise / 100:,.2f}",
        account_count=str(len(case.accounts)),
        bank_count=str(len(banks)),
        bank_list=", ".join(banks) if banks else "none recorded",
        location_count=str(len(locations)),
        location_list=", ".join(locations) if locations else "none recorded",
        first_seen=case.first_seen.isoformat(),
        last_seen=case.last_seen.isoformat(),
        single_complaint_note=(
            "This cluster is anchored by a single complaint so far."
            if case.single_complaint
            else ""
        ),
        disclaimer=_DISCLAIMER,
    ).strip()
