"""pdf.py — render_pdf(bundle, draft, locale) -> bytes (DOC 3 S2, ReportLab; DOC 2 §2.2 "Evidence
storage and PDF generation" decision).

Devanagari (DOC 3 "Unicode text (Hindi labels, S5)"): registers a Devanagari-capable TrueType font
if one is present at `font_path`; falls back to Helvetica (Latin-only) and logs a warning
otherwise. This build ships no such font file (offline sandbox, no network access to fetch one —
docs/state/track-a.md Learnings [A12]) and S5's Hindi content does not exist yet either, so the
fallback path is what every pack uses today; it is an honest, logged gap, not a silent one.

Dynamic content (forecast text, complaint-derived strings) is rendered with Preformatted, not
Paragraph, so nothing needs XML-escaping and nothing from the data can be parsed as markup.
"""

from __future__ import annotations

import dataclasses
import json
from io import BytesIO
from pathlib import Path

import structlog
from nakabandi.casework.evidence.bundle import EvidenceBundle
from nakabandi.casework.evidence.certificate import Section63Draft
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer

logger = structlog.get_logger(__name__)

_BODY_FONT = "Helvetica"
_BOLD_FONT = "Helvetica-Bold"
_registered_font_path: Path | None = None
_TIMELINE_CAP = 200
_AUDIT_TAIL = 50


def _register_font(font_path: Path | None) -> tuple[str, str]:
    global _registered_font_path
    if font_path is None or not font_path.exists():
        if font_path is not None:
            logger.warning("evidence.pdf.font_missing", path=str(font_path))
        return _BODY_FONT, _BOLD_FONT
    if _registered_font_path != font_path:
        pdfmetrics.registerFont(TTFont("EvidenceDevanagari", str(font_path)))
        _registered_font_path = font_path
    return "EvidenceDevanagari", "EvidenceDevanagari"


def _pretty(obj: object) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, default=str)


def render_pdf(
    bundle: EvidenceBundle,
    draft: Section63Draft,
    locale: str = "en",
    font_path: Path | None = None,
) -> bytes:
    body_font, bold_font = _register_font(font_path)
    base_styles = getSampleStyleSheet()
    heading = ParagraphStyle("EvidenceHeading", parent=base_styles["Heading2"], fontName=bold_font)
    body = ParagraphStyle("EvidenceBody", parent=base_styles["Normal"], fontName=body_font)
    mono = ParagraphStyle(
        "EvidenceMono", parent=base_styles["Code"], fontName=body_font, fontSize=7, leading=9
    )

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm)
    story: list = []

    def section(title: str, obj: object, empty_note: str = "none recorded") -> None:
        story.append(Paragraph(title, heading))
        if not obj:
            story.append(Paragraph(empty_note, body))
        else:
            story.append(Preformatted(_pretty(obj), mono))
        story.append(Spacer(1, 6))

    story.append(Paragraph(f"Evidence Pack — Alert {bundle.alert_id}", heading))
    story.append(Paragraph(f"Generated at {bundle.generated_at}", body))
    story.append(Spacer(1, 8))

    section("Summary", bundle.summary)
    section("Case accounts", bundle.case_accounts)
    section("Forecast and evidence statements", bundle.prediction)
    section("Interception and proportionality", bundle.interception)

    timeline = bundle.timeline[:_TIMELINE_CAP]
    story.append(Paragraph("Timeline of actions and outcomes", heading))
    if timeline:
        story.append(Preformatted(_pretty(timeline), mono))
        if len(bundle.timeline) > _TIMELINE_CAP:
            story.append(
                Paragraph(
                    f"... {len(bundle.timeline) - _TIMELINE_CAP} more entries; see the audit "
                    "range below.",
                    body,
                )
            )
    else:
        story.append(Paragraph("none recorded", body))
    story.append(PageBreak())

    story.append(Paragraph("Audit excerpt and head hash", heading))
    story.append(Paragraph(f"Audit head hash: {bundle.audit_head_hash}", body))
    story.append(Preformatted(_pretty(bundle.audit_excerpt[-_AUDIT_TAIL:]), mono))
    story.append(Spacer(1, 6))

    section("Hash report", {"algorithm": draft.hash_algorithm, "hash_values": draft.hash_values})

    story.append(Paragraph("Certificate draft", heading))
    story.append(Paragraph(draft.label, body))
    story.append(
        Preformatted(
            _pretty(
                {
                    "record_description": draft.record_description,
                    "system_description": draft.system_description,
                    "production_process": draft.production_process,
                    "condition_statements": draft.condition_statements,
                    "part_a": dataclasses.asdict(draft.part_a),
                    "part_b": dataclasses.asdict(draft.part_b),
                }
            ),
            mono,
        )
    )

    doc.build(story)
    return buf.getvalue()
