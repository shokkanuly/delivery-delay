"""Public evaluation example: reproducible synthetic evidence, no credential bypass."""
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app
from api.schemas import HistoryAuditOut
from scripts.build_demo_report import SOURCE, TARGET, demo_snapshot


def test_public_sample_is_tied_to_exact_csv_and_known_answers():
    snapshot = json.loads(TARGET.read_text(encoding="utf-8"))
    assert snapshot == demo_snapshot()
    assert snapshot["source_sha256"] == hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    assert SOURCE.read_bytes() == (Path(__file__).parent / "fixtures/1c_export_cp1251.csv").read_bytes()
    report = HistoryAuditOut(**snapshot["report"])
    assert report.data_source == "synthetic_upload"
    assert (report.quality.rows_total, report.quality.rows_kept, report.quality.rows_dropped) == (12, 8, 4)
    assert len(report.scorecard) == 5
    assert report.backtest.status == "insufficient_data"
    assert report.backtest.beats_baseline is None
    assert report.saved is False and report.audit_id is None


def test_uploaded_fixture_and_public_example_use_the_same_rules(api_client):
    response = api_client.post("/audit/history", data={"synthetic": "true"},
                               files={"file": (SOURCE.name, SOURCE.read_bytes(), "text/csv")})
    assert response.status_code == 200, response.text
    expected = HistoryAuditOut(**demo_snapshot()["report"]).model_dump(mode="json")
    assert response.json() == expected


def test_sample_is_public_while_upload_remains_authenticated(monkeypatch):
    monkeypatch.setenv("SITEPULSE_ADMIN_KEY", "operator-only-test-key")
    client = TestClient(app)
    public = client.get("/static/samples/audit_report_synthetic.json")
    assert public.status_code == 200
    assert public.json()["report"]["data_source"] == "synthetic_upload"
    upload = client.post("/audit/history", files={"file": (SOURCE.name, SOURCE.read_bytes(), "text/csv")})
    assert upload.status_code == 401
    assert "operator-only-test-key" not in public.text
