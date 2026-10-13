"""README rule 1: calls only go down. Domain engines (ml/, engines/, business/)
must not import the web or UI layers, so each stays testable on its own."""
from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
FORBIDDEN = {"fastapi", "starlette", "streamlit", "requests", "api", "dashboard"}
ENGINE_FILES = [p for pkg in ("ml", "engines", "business") for p in (ROOT / pkg).rglob("*.py")]


@pytest.mark.parametrize("path", ENGINE_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_engines_do_not_import_upper_layers(path):
    tree = ast.parse(path.read_text())
    names = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not names & FORBIDDEN, f"{path.name} imports {names & FORBIDDEN}"
