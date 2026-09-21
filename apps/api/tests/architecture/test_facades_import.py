"""Scaffold smoke test: every module facade named in DOC 2 §2.1 imports cleanly."""

import importlib

import pytest

MODULES = [
    "shared", "geo", "intake", "graph", "forecast", "interception",
    "alerting", "casework", "access", "audit", "analytics", "evaluation", "pipeline",
]  # fmt: skip


@pytest.mark.parametrize("module", MODULES)
def test_facade_imports(module: str) -> None:
    importlib.import_module(f"nakabandi.{module}")


def test_composition_root_imports() -> None:
    importlib.import_module("nakabandi.main")
