"""UI <-> API contract for company workspaces.

Both UIs once posted field names the schema did not have (every save was a
422) and read fields outside the `{found, workspace}` envelope (the form never
loaded). These tests pin the contract from the API side; the UIs send exactly
`CompanyWorkspaceIn` fields.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.schemas import CompanyWorkspaceIn
from business import economics


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import api.main as main
    monkeypatch.setattr(main, "WORKSPACES_FILE", tmp_path / "workspaces.json")
    return TestClient(main.app)


def _payload(**over):
    base = {"access_key": "T-1", "company_name": "Co", "project_id": "PRJ_002",
            "project_name": "Site", "location": "Astana",
            **economics.DEMO_SITE_INPUTS}
    return {**base, **over}


def test_save_then_load_round_trip(client):
    r = client.post("/projects/workspace", json=_payload(cranes_count=3))
    assert r.status_code == 200, r.text
    got = client.get("/projects/workspace/T-1").json()
    assert got["found"] is True
    assert got["workspace"]["cranes_count"] == 3


def test_finance_is_computed_on_read_not_stored(client, tmp_path):
    client.post("/projects/workspace", json=_payload())
    stored = (tmp_path / "workspaces.json").read_text()
    assert "finance" not in stored
    ws = client.get("/projects/workspace/T-1").json()["workspace"]
    assert ws["finance"] == economics.site_finance(ws)


def test_stateless_site_calc_matches_module(client):
    body = client.post("/economics/site", json=economics.DEMO_SITE_INPUTS).json()
    assert body == economics.site_finance(economics.DEMO_SITE_INPUTS)


def test_legacy_ui_field_names_are_rejected(client):
    """The old UI shape must fail loudly, not be silently half-read."""
    r = client.post("/projects/workspace", json={
        "access_key": "T-2", "company_name": "Co", "project_name": "S",
        "location": "L", "tower_cranes_count": 4, "crane_daily_rate_usd": 1.0})
    assert r.status_code == 422


def test_ui_payload_keys_are_schema_fields():
    """Every key the two UIs send must exist on the schema."""
    import pathlib
    import re
    root = pathlib.Path(__file__).resolve().parent.parent
    fields = set(CompanyWorkspaceIn.model_fields)
    js = (root / "static" / "index.html").read_text()
    js_keys = set()
    for fn, opener in [("async function saveCompanyWorkspace", "const payload = {"),
                       ("function readWorkspaceForm", "return {")]:
        block = js[js.index(fn):]
        block = block[block.index(opener):block.index("};")]
        js_keys |= set(re.findall(r"^\s*(\w+):", block, re.M))
    py = (root / "dashboard" / "app.py").read_text()
    pblock = py[py.index("ws_payload = {"):]
    pblock = pblock[:pblock.index("}")]
    py_keys = set(re.findall(r'"(\w+)":', pblock))
    assert js_keys and js_keys <= fields, js_keys - fields
    assert py_keys and py_keys <= fields, py_keys - fields
