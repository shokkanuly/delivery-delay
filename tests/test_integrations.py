"""Signed gate/1C ingest, review queue and audit log (patterns ported from JanaМен / shokkanuly/posttech)."""
from __future__ import annotations

import json
import time

import pytest

from api import signing

SECRET = "s" * 40
PATH = "/integrations/gate-events"


@pytest.fixture()
def ingest_client(api_client, monkeypatch):
    monkeypatch.setenv("SITEPULSE_INGEST_KEYS", f"gate-1:{SECRET}")
    return api_client


def post_signed(client, payload, *, key=SECRET, nonce=None, now=None):
    body = json.dumps(payload).encode()
    headers = signing.sign("gate-1", key, "POST", PATH, body, now=now, nonce=nonce)
    return client.post(PATH, content=body, headers={**headers, "Content-Type": "application/json"})


def serve_prediction(client, ref: str, promised: str = "2026-10-10"):
    r = client.post("/predict", json={"delivery_ref": ref, "supplier_id": "S01", "material_type": "steel",
                                      "quantity": 10, "order_date": "2026-10-01", "promised_date": promised,
                                      "route_type": "local"})
    assert r.status_code == 200, r.text


class TestSigning:
    def test_roundtrip_and_tamper(self):
        body = b'{"a":1}'
        h = {k.lower(): v for k, v in signing.sign("k", SECRET, "POST", PATH, body).items()}
        assert signing.verify(h, {"k": SECRET}, "POST", PATH, body)
        with pytest.raises(signing.SignatureError):
            signing.verify(h, {"k": SECRET}, "POST", PATH, b'{"a":2}')
        with pytest.raises(signing.SignatureError):
            old = {k.lower(): v for k, v in signing.sign("k", SECRET, "POST", PATH, body, now=time.time() - 3600).items()}
            signing.verify(old, {"k": SECRET}, "POST", PATH, body)

    def test_short_secrets_ignored(self):
        assert signing.keys_from_env("a:short,b:" + "x" * 32) == {"b": "x" * 32}


class TestGateEvents:
    def test_disabled_without_keys(self, api_client, monkeypatch):
        monkeypatch.delenv("SITEPULSE_INGEST_KEYS", raising=False)
        assert post_signed(api_client, {"events": []}).status_code == 503

    def test_bad_signature_and_replay(self, ingest_client):
        ev = {"events": [{"event_id": "e1", "delivery_ref": "D-1", "occurred_on": "2026-10-12"}]}
        assert post_signed(ingest_client, ev, key="w" * 40).status_code == 401
        nonce = "n" * 32
        assert post_signed(ingest_client, ev, nonce=nonce).status_code == 200
        assert post_signed(ingest_client, ev, nonce=nonce).status_code == 409

    def test_arrival_closes_the_loop_idempotently(self, ingest_client):
        serve_prediction(ingest_client, "D-100", promised="2026-10-10")
        batch = {"events": [
            {"event_id": "e100", "delivery_ref": "D-100", "occurred_on": "2026-10-14", "gate": "North"},
            {"event_id": "e100", "delivery_ref": "D-100", "occurred_on": "2026-10-14"},       # same event twice
            {"event_id": "e999", "delivery_ref": "UNKNOWN-REF", "occurred_on": "2026-10-14"},  # no prediction
        ]}
        r = post_signed(ingest_client, batch)
        assert r.json() == {"applied": 1, "unmatched": 1, "duplicate": 1}, r.text
        # A retried push of the whole batch changes nothing.
        assert post_signed(ingest_client, batch).json() == {"applied": 0, "unmatched": 0, "duplicate": 3}

        preds = ingest_client.get("/predictions").json()["predictions"]
        row = next(p for p in preds if p["delivery_ref"] == "D-100")
        assert row["actual_late"] == 1  # 4 days late, grace 1
        assert ingest_client.get("/accuracy").json()["with_known_outcome"] == 1

        review = ingest_client.get("/integrations/review").json()
        assert [e["delivery_ref"] for e in review["events"]] == ["UNKNOWN-REF"]
        st = ingest_client.get("/integrations/status").json()
        assert st["events"] == {"applied": 1, "unmatched": 1} and st["configured_senders"] == 1
        audit = ingest_client.get("/integrations/audit").json()["events"]
        assert audit[0]["actor"] == "ingest:gate-1" and audit[0]["action"] == "gate_events.received"

    def test_invalid_payload_is_422(self, ingest_client):
        assert post_signed(ingest_client, {"events": [{"event_id": "x"}]}).status_code == 422

    def test_admin_views_need_key(self, ingest_client):
        from fastapi.testclient import TestClient
        import api.main as main
        with TestClient(main.app) as anon:
            assert anon.get("/integrations/review").status_code == 401
            assert anon.get("/integrations/audit").status_code == 401

    def test_manual_outcomes_are_audited(self, api_client):
        serve_prediction(api_client, "D-200")
        r = api_client.post("/outcomes", json=[{"delivery_ref": "D-200", "actual_date": "2026-10-10"}])
        assert r.json()["updated"] == 1
        assert api_client.get("/integrations/audit").json()["events"][0]["action"] == "outcomes.recorded"
