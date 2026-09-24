"""Unit tests (DOC 3 S2 testing plan): hash_report is reproducible; Section63Draft always carries
the DRAFT label; FileStore round-trips; render_pdf produces a real PDF."""

from __future__ import annotations

from pathlib import Path

from nakabandi.casework.evidence.bundle import EvidenceBundle
from nakabandi.casework.evidence.certificate import DRAFT_LABEL, build_certificate
from nakabandi.casework.evidence.file_store import LocalFileStore
from nakabandi.casework.evidence.hashing import hash_report
from nakabandi.casework.evidence.pdf import render_pdf


def test_hash_report_is_reproducible() -> None:
    components = {"evidence_bundle.json": b'{"a": 1}', "extra.txt": b"hello world"}

    first = hash_report(components)
    second = hash_report(dict(components))  # a fresh dict, same content

    assert first.bundle_sha256 == second.bundle_sha256
    assert [i.sha256 for i in first.items] == [i.sha256 for i in second.items]


def test_hash_report_changes_with_content() -> None:
    a = hash_report({"x.json": b"one"})
    b = hash_report({"x.json": b"two"})
    assert a.bundle_sha256 != b.bundle_sha256


def test_certificate_always_carries_the_draft_label() -> None:
    draft = build_certificate("a record", "SHA-256", ["abc123"])
    assert draft.label == DRAFT_LABEL
    assert "DRAFT" in draft.label


def test_local_file_store_round_trips(tmp_path: Path) -> None:
    store = LocalFileStore(tmp_path / "evidence")
    store.save("alert-1/v1/pack.pdf", b"%PDF-fake-bytes")
    assert store.read("alert-1/v1/pack.pdf") == b"%PDF-fake-bytes"


def test_file_store_refuses_a_path_that_escapes_its_root(tmp_path: Path) -> None:
    store = LocalFileStore(tmp_path / "evidence")
    try:
        store.save("../escape.pdf", b"x")
    except ValueError:
        pass
    else:
        raise AssertionError("expected a ValueError for a path escaping the store root")


def test_render_pdf_produces_a_real_pdf() -> None:
    bundle = EvidenceBundle(
        alert_id="al-1",
        generated_at="2026-01-15T10:00:00+00:00",
        summary={"alert_id": "al-1", "severity": "high"},
        prediction={"id": "f-1", "confidence": 0.8},
        interception=[{"id": "ia-1", "verdict": "INTERCEPTABLE"}],
        timeline=[{"at": "2026-01-15T10:00:00+00:00", "kind": "raised", "text_code": "x"}],
        actions=[],
        outcomes=[],
        audit_excerpt=[{"seq": 1, "action": "alert.raised"}],
        audit_head_hash="deadbeef",
        case_accounts=[{"masked_ref": "****7890", "bank_id": "bank-1", "complaint_count": 2}],
    )
    draft = build_certificate("evidence pack for al-1", "SHA-256", ["deadbeef"])

    pdf_bytes = render_pdf(bundle, draft)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500
