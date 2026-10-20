"""Stage 3 (docs/plans/mvp-reshape.md): POST /audit/history.

Covers the Done when of Stage 3: the curl-equivalent call on
tests/fixtures/1c_export_cp1251.csv returns the three blocks (quality,
scorecard, backtest); an API test covers it (this file).
"""
from __future__ import annotations

import pathlib

import pytest

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "1c_export_cp1251.csv"


def _upload(client, **params):
    with FIXTURE.open("rb") as f:
        return client.post("/audit/history", params=params,
                           files={"file": ("1c_export_cp1251.csv", f, "text/csv")})


class TestAuditHistory:
    def test_returns_the_three_blocks(self, api_client):
        """The exact Done when: upload the Stage 1 fixture, get back quality +
        scorecard + backtest."""
        r = _upload(api_client)
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body) >= {"quality", "scorecard", "backtest"}

    def test_quality_matches_stage_1(self, api_client):
        """Same fixture, same numbers test_ingest_profile.py already pins."""
        body = _upload(api_client).json()
        q = body["quality"]
        assert q["rows_total"] == 12
        assert q["rows_kept"] == 8
        assert q["bad_dates"] == 2
        assert q["duplicates"] == 1

    def test_scorecard_has_a_row_per_supplier(self, api_client):
        body = _upload(api_client).json()
        suppliers = body["scorecard"]["suppliers"]
        assert len(suppliers) == 5          # 5 distinct suppliers across the 8 kept rows
        assert {"on_time_share", "on_time_ci_low", "on_time_ci_high"} <= set(suppliers[0])
        assert body["scorecard"]["by_material"]

    def test_backtest_skips_honestly_on_too_little_data(self, api_client):
        """8 kept rows cannot support an honest 70/30 time split -- the
        endpoint must say so, not fabricate a PR-AUC."""
        body = _upload(api_client).json()
        assert body["backtest"]["skipped"] is True
        assert "reason" in body["backtest"]
        assert body["model_beats_baseline"] is None

    def test_json_is_cyrillic_safe(self, api_client):
        """Supplier/material names are Cyrillic -- must round-trip, not
        mojibake or raise."""
        body = _upload(api_client).json()
        names = {row["supplier_id"] for row in body["scorecard"]["suppliers"]}
        assert any("ТОО" in n or "ИП" in n or "ООО" in n for n in names)

    def test_missing_required_column_is_400_with_russian_name(self, api_client):
        bad = "Поставщик;Количество\nA;5\n".encode("utf-8")
        r = api_client.post("/audit/history", files={"file": ("bad.csv", bad, "text/csv")})
        assert r.status_code == 400
        assert "Номенклатура" in r.json()["detail"]

    def test_requires_admin_key(self, temp_db, monkeypatch):
        """No X-API-Key -> 401, same as every other admin endpoint
        (tests/test_security.py covers the no-key-configured-at-all 503)."""
        from fastapi.testclient import TestClient
        import api.main as main
        monkeypatch.setenv("SITEPULSE_ADMIN_KEY", "right")
        client = TestClient(main.app)
        with FIXTURE.open("rb") as f:
            r = client.post("/audit/history", files={"file": ("x.csv", f, "text/csv")})
        assert r.status_code == 401

    def test_nothing_saved_by_default(self, api_client):
        body = _upload(api_client).json()
        assert body["saved_to"] is None

    def test_save_true_persists_the_upload(self, api_client, tmp_path, monkeypatch):
        import api.routers.audit as audit_mod
        monkeypatch.setattr(audit_mod, "UPLOAD_DIR", tmp_path / "customer_uploads")

        body = _upload(api_client, save="true").json()
        assert body["saved_to"] is not None
        saved_path = pathlib.Path(body["saved_to"])
        assert saved_path.exists()
        assert saved_path.read_bytes() == FIXTURE.read_bytes()

    def test_file_too_large_is_413(self, api_client, monkeypatch):
        import api.routers.audit as audit_mod
        monkeypatch.setattr(audit_mod, "MAX_UPLOAD_BYTES", 10)
        r = api_client.post("/audit/history", files={"file": ("big.csv", b"x" * 100, "text/csv")})
        assert r.status_code == 413


class TestTimeSplitBacktestOnEnoughData:
    """ml.train.time_split_backtest directly, on enough rows to actually run
    (the API test above only exercises the honest-skip path)."""

    def test_runs_and_reports_monotonic_calibration(self):
        from ml.data_sim import generate_deliveries
        from ml.train import time_split_backtest

        df = generate_deliveries(n=600, seed=11)
        result = time_split_backtest(df)

        assert result["skipped"] is False
        assert result["train_rows"] > 0 and result["test_rows"] > 0
        assert 0.0 <= result["model_pr_auc"] <= 1.0
        assert 0.0 <= result["baseline_pr_auc"] <= 1.0
        assert result["beats_baseline"] == (result["model_pr_auc"] > result["baseline_pr_auc"])
        cal = result["calibration"]
        rates = [cal[b]["actually_late_share"] for b in ("green", "yellow", "red")
                if cal[b]["actually_late_share"] is not None]
        assert rates == sorted(rates), "red must run late at least as often as green"

    def test_never_writes_the_production_artifact(self, tmp_path):
        """The backtest must not touch ml.train.ARTIFACT_PATH -- that's the
        one /predict serves, and a customer's data must never leak into it."""
        from ml.data_sim import generate_deliveries
        from ml.train import ARTIFACT_PATH, time_split_backtest

        before = ARTIFACT_PATH.read_bytes() if ARTIFACT_PATH.exists() else None
        time_split_backtest(generate_deliveries(n=600, seed=3))
        after = ARTIFACT_PATH.read_bytes() if ARTIFACT_PATH.exists() else None
        assert before == after

    def test_too_few_rows_skips_with_a_reason(self):
        from ml.data_sim import generate_deliveries
        from ml.train import time_split_backtest

        result = time_split_backtest(generate_deliveries(n=20, seed=1))
        assert result["skipped"] is True
        assert "reason" in result
