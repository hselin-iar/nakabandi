"""English templates for outbound messages (DOC 4 A8; S5 adds Hindi under templates/hi/).

Bodies are stored on the Delivery for the Outbox viewer, so every parameter passed in must
already be safe to show there (masked identifiers only, DOC 4 A8 drift warning)."""

from __future__ import annotations

from pathlib import Path
from string import Template

_TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


class FileTemplateRenderer:
    def __init__(self, root: Path = _TEMPLATES) -> None:
        self._root = root

    def render(self, kind: str, locale: str, **params: str) -> str:
        path = self._root / locale / f"{kind}.txt"
        return Template(path.read_text(encoding="utf-8")).substitute(params).strip()
