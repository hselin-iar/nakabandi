"""pdf.py — render_pdf(bundle, draft, locale) -> bytes (DOC 3 S2, ReportLab; DOC 2 §2.2 "Evidence
storage and PDF generation" decision).

Devanagari (DOC 3 "Unicode text (Hindi labels, S5)"): registers a Devanagari-capable TrueType font
if one is present at `font_path`; falls back to Helvetica (Latin-only) and logs a warning
otherwise. This build ships no such font file (offline sandbox, no network access to fetch one —
docs/state/track-a.md Learnings [A12]) and S5's Hindi content does not exist yet either, so the
fallback path is what every pack uses today; it is an honest, logged gap, not a silent one.

Layout: every section is rendered as labelled fields, tables and prose — not a raw JSON dump.
Every dynamic (DB- or complaint-derived) string is passed through `_esc` (XML-escape) before it
reaches a `Paragraph`, since ReportLab's mini-XML parser would otherwise treat stray `<`/`&` in
that data as markup; nothing from the data can be parsed as a tag. Bundle field access uses
`.get(...)` defaults throughout because not every alert has a forecast, an interception
assessment, or a populated audit/timeline — a partial bundle must still render, not crash.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import structlog
from nakabandi.casework.evidence.bundle import EvidenceBundle
from nakabandi.casework.evidence.certificate import Section63Draft
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = structlog.get_logger(__name__)

_BODY_FONT = "Helvetica"
_BOLD_FONT = "Helvetica-Bold"
_registered_font_path: Path | None = None
_TIMELINE_CAP = 200
_AUDIT_TAIL = 50
_CANDIDATES_SHOWN = 5
_LEVEL_ORDER = ("location", "cell", "district")
_GRID_COLOR = colors.HexColor("#cccccc")
_HEADER_BG = colors.HexColor("#eeeeee")


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


def _esc(value: object, empty: str = "—") -> str:
    """XML-escape any DB/complaint-derived value for safe use inside a Paragraph."""
    if value is None or value == "":
        return empty
    return escape(str(value))


def _pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return _esc(value)


class _Styles:
    def __init__(self, body_font: str, bold_font: str) -> None:
        base = getSampleStyleSheet()
        self.heading = ParagraphStyle("EvHeading", parent=base["Heading2"], fontName=bold_font)
        self.subheading = ParagraphStyle(
            "EvSubheading", parent=base["Heading3"], fontName=bold_font, fontSize=10
        )
        self.body = ParagraphStyle("EvBody", parent=base["Normal"], fontName=body_font)
        self.cell = ParagraphStyle("EvCell", parent=self.body, fontSize=8, leading=10)
        self.cell_head = ParagraphStyle("EvCellHead", parent=self.cell, fontName=bold_font)
        self.mono = ParagraphStyle(
            "EvMono", parent=base["Code"], fontName=body_font, fontSize=7, leading=9
        )


def _grid_table(
    header: list[str] | None, rows: list[list[str]], styles: _Styles, col_widths=None
) -> Table:
    data: list[list[Any]] = []
    if header:
        data.append([Paragraph(f"<b>{_esc(h)}</b>", styles.cell_head) for h in header])
    for row in rows:
        data.append([Paragraph(cell, styles.cell) for cell in row])
    table = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, _GRID_COLOR),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG))
    table.setStyle(TableStyle(style))
    return table


def _kv_table(pairs: list[tuple[str, str]], styles: _Styles) -> Table:
    rows = [
        [Paragraph(f"<b>{_esc(label)}</b>", styles.cell), Paragraph(_esc(value), styles.cell)]
        for label, value in pairs
    ]
    table = Table(rows, colWidths=[45 * mm, None])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, _GRID_COLOR),
            ]
        )
    )
    return table


def _bullets(items: list[str], styles: _Styles) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(_esc(text), styles.body)) for text in items],  # type: ignore[arg-type]
        bulletType="bullet",
        leftIndent=12,
    )


def _story_target(target: dict[str, Any]) -> str:
    kind = target.get("kind")
    name = target.get("name")
    tid = target.get("id")
    if name:
        return f"{name} ({kind}, {tid})" if kind or tid else str(name)
    return f"{kind} {tid}".strip() or "—"


def _summary_section(story: list, summary: dict[str, Any], styles: _Styles) -> None:
    story.append(Paragraph("Summary", styles.heading))
    if not summary:
        story.append(Paragraph("none recorded", styles.body))
        story.append(Spacer(1, 6))
        return
    target = summary.get("target") or {}
    pairs = [
        ("Alert ID", summary.get("alert_id")),
        ("Cluster reference", summary.get("cluster_ref")),
        ("Target", _story_target(target)),
        ("Severity", summary.get("severity")),
        ("Status", summary.get("status")),
        ("Ladder level", summary.get("ladder_level")),
        ("Created at", summary.get("created_at")),
    ]
    story.append(_kv_table(pairs, styles))
    story.append(Spacer(1, 6))


def _case_accounts_section(story: list, accounts: list[dict[str, Any]], styles: _Styles) -> None:
    story.append(Paragraph("Case accounts", styles.heading))
    if not accounts:
        story.append(Paragraph("none recorded", styles.body))
        story.append(Spacer(1, 6))
        return
    rows = [
        [_esc(a.get("masked_ref")), _esc(a.get("bank_id")), _esc(a.get("complaint_count"))]
        for a in accounts
    ]
    story.append(_grid_table(["Account ref", "Bank", "Complaints"], rows, styles))
    story.append(Spacer(1, 6))


def _forecast_section(story: list, prediction: dict[str, Any] | None, styles: _Styles) -> None:
    story.append(Paragraph("Forecast and evidence statements", styles.heading))
    if not prediction:
        story.append(Paragraph("no forecast available for this alert", styles.body))
        story.append(Spacer(1, 6))
        return

    model_versions = prediction.get("model_versions") or {}
    pairs = [
        ("Forecast ID", prediction.get("id")),
        ("Complaint ID", prediction.get("complaint_id")),
        ("Cluster ID", prediction.get("cluster_id")),
        ("Generated at", prediction.get("generated_at")),
        ("Location scorer model", model_versions.get("scorer")),
        ("Timing model", model_versions.get("timing")),
        ("Overall confidence", _pct(prediction.get("confidence"))),
        ("Novelty", prediction.get("novelty")),
        ("Stale", prediction.get("stale")),
    ]
    story.append(_kv_table(pairs, styles))
    story.append(Spacer(1, 4))

    levels: dict[str, Any] = prediction.get("levels") or {}
    ordered_keys = [k for k in _LEVEL_ORDER if k in levels] + [
        k for k in levels if k not in _LEVEL_ORDER
    ]
    for level_key in ordered_keys:
        level = levels[level_key] or {}
        title = f"Top candidates — {level_key}"
        if level.get("abstained"):
            title += " (model abstained)"
        story.append(Paragraph(title, styles.subheading))
        items = (level.get("items") or [])[:_CANDIDATES_SHOWN]
        if not items:
            story.append(Paragraph("no candidates", styles.body))
        else:
            rows = [
                [_esc(it.get("rank")), _esc(it.get("id")), _pct(it.get("prob"))] for it in items
            ]
            story.append(_grid_table(["Rank", "Candidate", "Probability"], rows, styles))
        story.append(Spacer(1, 4))

    timing = prediction.get("timing") or {}
    if timing:
        story.append(Paragraph("Cash-out timing window", styles.subheading))
        pairs = [
            ("Minutes elapsed since report", timing.get("elapsed_min")),
            ("Probability by 30 min", _pct(timing.get("p30"))),
            ("Probability by 60 min", _pct(timing.get("p60"))),
            ("Probability by 120 min", _pct(timing.get("p120"))),
            ("Residual probability mass", _pct(timing.get("residual_mass"))),
        ]
        story.append(_kv_table(pairs, styles))
        story.append(Spacer(1, 4))

    evidence = prediction.get("evidence") or []
    story.append(Paragraph("Evidence statements", styles.subheading))
    if not evidence:
        story.append(Paragraph("none recorded", styles.body))
    else:
        story.append(_bullets([e.get("text_en", "") for e in evidence], styles))
    story.append(Spacer(1, 6))


def _interception_section(story: list, assessments: list[dict[str, Any]], styles: _Styles) -> None:
    story.append(Paragraph("Interception and proportionality", styles.heading))
    if not assessments:
        story.append(Paragraph("no interception assessment recorded", styles.body))
        story.append(Spacer(1, 6))
        return
    for a in assessments:
        target = a.get("target") or {}
        unit = a.get("best_unit") or {}
        unit_desc = (
            f"{unit.get('unit_id')} ({unit.get('unit_kind')}), ETA {unit.get('eta_min')} min"
            if unit
            else "—"
        )
        pairs = [
            ("Assessment ID", a.get("id")),
            ("Target", _story_target(target) if target else a.get("target")),
            ("Channel", a.get("channel")),
            ("Window (min)", a.get("window_min")),
            ("Best unit", unit_desc),
            ("Interception probability", _pct(a.get("interception_probability"))),
            ("Verdict", a.get("verdict")),
            ("Ladder level", a.get("ladder_level")),
            ("Reason code", a.get("reason_code")),
        ]
        story.append(_kv_table(pairs, styles))
        story.append(Spacer(1, 6))


def _actions_outcomes_section(
    story: list, actions: list[dict[str, Any]], outcomes: list[dict[str, Any]], styles: _Styles
) -> None:
    story.append(Paragraph("Officer actions", styles.heading))
    if not actions:
        story.append(Paragraph("none recorded", styles.body))
    else:
        rows = [
            [
                _esc(a.get("type")),
                _esc(a.get("status")),
                _esc(a.get("actor_role")),
                _esc(a.get("at")),
                _esc(a.get("note")),
            ]
            for a in actions
        ]
        story.append(_grid_table(["Type", "Status", "Actor role", "At", "Note"], rows, styles))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Recorded outcomes", styles.heading))
    if not outcomes:
        story.append(Paragraph("none recorded", styles.body))
    else:
        rows = [
            [
                _esc(o.get("result")),
                _esc(o.get("source")),
                _esc(o.get("decided_at")),
                _esc(o.get("reason")),
            ]
            for o in outcomes
        ]
        story.append(_grid_table(["Result", "Source", "Decided at", "Reason"], rows, styles))
    story.append(Spacer(1, 6))


def _timeline_section(story: list, timeline: list[dict[str, Any]], styles: _Styles) -> None:
    story.append(Paragraph("Timeline of actions and outcomes", styles.heading))
    capped = timeline[:_TIMELINE_CAP]
    if not capped:
        story.append(Paragraph("none recorded", styles.body))
        return
    rows = [[_esc(t.get("at")), _esc(t.get("kind")), _esc(t.get("text_code"))] for t in capped]
    story.append(_grid_table(["At", "Event", "Detail"], rows, styles))
    if len(timeline) > _TIMELINE_CAP:
        story.append(
            Paragraph(
                f"... {len(timeline) - _TIMELINE_CAP} more entries; see the audit range below.",
                styles.body,
            )
        )


def _audit_section(
    story: list, audit_excerpt: list[dict[str, Any]], head_hash: str, styles: _Styles
) -> None:
    story.append(Paragraph("Audit excerpt and head hash", styles.heading))
    story.append(Paragraph(f"Audit head hash: {_esc(head_hash)}", styles.mono))
    story.append(Spacer(1, 4))
    tail = audit_excerpt[-_AUDIT_TAIL:]
    if not tail:
        story.append(Paragraph("none recorded", styles.body))
        return
    rows = [
        [
            _esc(e.get("seq")),
            _esc(e.get("at")),
            _esc(e.get("action")),
            _esc(f"{e.get('entity_type', '')} {e.get('entity_id', '')}".strip()),
            _esc(e.get("hash")),
        ]
        for e in tail
    ]
    col_widths = [10 * mm, 30 * mm, 25 * mm, 35 * mm, None]
    story.append(_grid_table(["Seq", "At", "Action", "Entity", "Hash"], rows, styles, col_widths))
    if len(audit_excerpt) > _AUDIT_TAIL:
        story.append(
            Paragraph(
                f"... {len(audit_excerpt) - _AUDIT_TAIL} earlier entries not shown.", styles.body
            )
        )


def _hash_report_section(
    story: list, algorithm: str, hash_values: list[str], styles: _Styles
) -> None:
    story.append(Paragraph("Hash report", styles.heading))
    story.append(Paragraph(f"Algorithm: {_esc(algorithm)}", styles.body))
    if not hash_values:
        story.append(Paragraph("none recorded", styles.body))
    else:
        for h in hash_values:
            story.append(Preformatted(_esc(h, empty=""), styles.mono))
    story.append(Spacer(1, 6))


def _signatory_block(title: str, part: Any, styles: _Styles) -> list:
    block: list = [Paragraph(title, styles.subheading)]
    pairs = [
        ("Role", part.role),
        ("Name", part.name),
        ("Designation", part.designation),
        ("Qualification", part.qualification),
        ("Signature", part.signature),
    ]
    block.append(_kv_table(pairs, styles))
    block.append(Spacer(1, 4))
    return block


def _certificate_section(story: list, draft: Section63Draft, styles: _Styles) -> None:
    story.append(Paragraph("Certificate draft", styles.heading))
    story.append(Paragraph(f"<i>{_esc(draft.label)}</i>", styles.body))
    story.append(Spacer(1, 4))

    story.append(Paragraph("Record description", styles.subheading))
    story.append(Paragraph(_esc(draft.record_description), styles.body))
    story.append(Paragraph("System description", styles.subheading))
    story.append(Paragraph(_esc(draft.system_description), styles.body))
    story.append(Paragraph("Production process", styles.subheading))
    story.append(Paragraph(_esc(draft.production_process), styles.body))
    story.append(Spacer(1, 4))

    story.append(Paragraph("Condition statements", styles.subheading))
    if draft.condition_statements:
        story.append(_bullets(draft.condition_statements, styles))
    else:
        story.append(Paragraph("none recorded", styles.body))
    story.append(Spacer(1, 6))

    story.extend(_signatory_block("Part A — person in charge", draft.part_a, styles))
    story.extend(_signatory_block("Part B — expert", draft.part_b, styles))


def render_pdf(
    bundle: EvidenceBundle,
    draft: Section63Draft,
    locale: str = "en",
    font_path: Path | None = None,
) -> bytes:
    body_font, bold_font = _register_font(font_path)
    styles = _Styles(body_font, bold_font)

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm)
    story: list = []

    story.append(Paragraph(f"Evidence Pack — Alert {_esc(bundle.alert_id)}", styles.heading))
    story.append(Paragraph(f"Generated at {_esc(bundle.generated_at)}", styles.body))
    story.append(Spacer(1, 8))

    _summary_section(story, bundle.summary, styles)
    _case_accounts_section(story, bundle.case_accounts, styles)
    _forecast_section(story, bundle.prediction, styles)
    _interception_section(story, bundle.interception, styles)
    _actions_outcomes_section(story, bundle.actions, bundle.outcomes, styles)
    _timeline_section(story, bundle.timeline, styles)
    story.append(PageBreak())

    _audit_section(story, bundle.audit_excerpt, bundle.audit_head_hash, styles)
    story.append(Spacer(1, 6))
    _hash_report_section(story, draft.hash_algorithm, draft.hash_values, styles)
    _certificate_section(story, draft, styles)

    doc.build(story)
    return buf.getvalue()
