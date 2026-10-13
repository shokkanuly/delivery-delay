"""UI <-> API contract for company workspaces, stored in the `workspaces` table.

Both UIs once posted field names the schema did not have (every save was a
422) and read fields outside the `{found, workspace}` envelope. Workspaces
then lived in a git-tracked JSON file that even GET requests rewrote. These
tests pin the contract, the storage and the access rules.
"""
from __future__ import annotations

import pathlib
import re

import pytest
from fastapi.testclient import TestClient

from api.schemas import CompanyWorkspaceIn
from business import economics

ROOT = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture()
def client(temp_db):
    import api.main as main
    return TestClient(main.app)


def _payload(**over):
    base = {"company_name": "Co", "project_id": "PRJ_002", "project_name": "Site",
            "location": "Astana", **economics.DEMO_SITE_INPUTS}
    return {**base, **over}


def test_blank_key_creates_with_a_server_issued_key(client):
    r = client.post("/projects/workspace", json=_payload())
    assert r.status_code == 200, r.text
    key = r.json()["access_key"]
    assert key.startswith("WS-") and len(key) >= 20
    got = client.get(f"/projects/workspace/{key}").json()
    assert got["found"] and got["workspace"]["cranes_count"] == 6


def test_update_with_issued_key(client):
    key = client.post("/projects/workspace", json=_payload()).json()["access_key"]
    r = client.post("/projects/workspace", json=_payload(access_key=key, cranes_count=3))
    assert r.json()["status"] == "saved"
    assert client.get(f"/projects/workspace/{key}").json()["workspace"]["cranes_count"] == 3


def test_cannot_choose_or_guess_a_key(client):
    assert client.post("/projects/workspace", json=_payload(access_key="MY-KEY")).status_code == 404


def test_demo_workspaces_are_read_only(temp_db, client):
    temp_db["seed"].seed()
    assert client.get("/projects/workspace/DEMO-SITE-B-2026").json()["workspace"]["read_only"]
    r = client.post("/projects/workspace", json=_payload(access_key="DEMO-SITE-B-2026"))
    assert r.status_code == 403


def test_get_has_no_side_effects(temp_db, client):
    assert client.get("/projects/workspace/DEMO-ANYTHING").status_code == 404
    with temp_db["Session"]() as s:
        assert s.query(temp_db["models"].Workspace).count() == 0


def test_finance_is_derived_not_stored(temp_db, client):
    key = client.post("/projects/workspace", json=_payload()).json()["access_key"]
    with temp_db["Session"]() as s:
        assert "finance" not in s.get(temp_db["models"].Workspace, key).inputs
    ws = client.get(f"/projects/workspace/{key}").json()["workspace"]
    assert ws["finance"] == economics.site_finance(economics.DEMO_SITE_INPUTS)


def test_stateless_site_calc_matches_module(client):
    body = client.post("/economics/site", json=economics.DEMO_SITE_INPUTS).json()
    assert body == economics.site_finance(economics.DEMO_SITE_INPUTS)


def test_legacy_ui_field_names_are_rejected(client):
    r = client.post("/projects/workspace", json={
        "company_name": "Co", "project_name": "S", "location": "L",
        "tower_cranes_count": 4, "crane_daily_rate_usd": 1.0})
    assert r.status_code == 422


def test_no_runtime_json_store():
    assert not (ROOT / "data" / "workspaces.json").exists()
    assert "workspaces.json" not in (ROOT / "api" / "routers" / "business.py").read_text()


def test_ui_payload_keys_are_schema_fields():
    fields = set(CompanyWorkspaceIn.model_fields)
    js = (ROOT / "static" / "index.html").read_text()
    js_keys = set()
    for fn, opener in [("async function saveCompanyWorkspace", "const payload = {"),
                       ("function readWorkspaceForm", "return {")]:
        block = js[js.index(fn):]
        block = block[block.index(opener):block.index("};")]
        js_keys |= set(re.findall(r"^\s*(\w+):", block, re.M))
    py = (ROOT / "dashboard" / "app.py").read_text()
    pblock = py[py.index("ws_payload = {"):]
    pblock = pblock[:pblock.index("}")]
    py_keys = set(re.findall(r'"(\w+)":', pblock))
    assert js_keys and js_keys <= fields, js_keys - fields
    assert py_keys and py_keys <= fields, py_keys - fields
