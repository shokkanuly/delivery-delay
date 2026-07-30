"""API smoke tests across all three engines, plus the evidence loop."""
from __future__ import annotations

SAMPLE = {"supplier_id": "SUP_004", "material_type": "rebar", "route_type": "intercity",
          "quantity": 50, "order_date": "2026-05-01", "promised_date": "2026-05-20"}

CSV_HEADER = ("supplier_id,material_type,route_type,quantity,order_date,promised_date\n")


class TestHealthAndMetrics:
    def test_health_lists_three_engines(self, api_client):
        j = api_client.get("/health").json()
        assert j["status"] == "ok"
        assert set(j["engines"]) == {"delay_prediction", "resource_scheduler",
                                     "sequence_validator"}

    def test_metrics_reports_baseline_comparison(self, api_client):
        j = api_client.get("/metrics").json()
        assert {"baseline", "model", "lift"} <= set(j["ap"])
        assert j["model_version"]


class TestPredict:
    def test_single_prediction_shape(self, api_client):
        j = api_client.post("/predict", json=SAMPLE).json()
        assert 0.0 <= j["risk"] <= 1.0
        assert j["risk_band"] in {"green", "yellow", "red"}
        assert isinstance(j["drivers"], list)

    def test_unknown_supplier_still_scores(self, api_client):
        """Cold start must not 500 -- a brand-new supplier is normal."""
        r = api_client.post("/predict", json={**SAMPLE, "supplier_id": "BRAND_NEW"})
        assert r.status_code == 200
        assert r.json()["supplier_n_prior"] == 0

    def test_invalid_payload_rejected(self, api_client):
        assert api_client.post("/predict", json={"supplier_id": "S1"}).status_code == 422

    def test_batch_sorted_by_risk_descending(self, api_client):
        csv = CSV_HEADER + \
            "SUP_004,rebar,cross_border,50,2026-01-02,2026-01-09\n" \
            "SUP_001,timber,urban,10,2026-06-01,2026-07-15\n"
        rows = api_client.post("/predict/batch",
                               files={"file": ("d.csv", csv, "text/csv")}).json()["rows"]
        assert rows == sorted(rows, key=lambda r: r["risk"], reverse=True)

    def test_batch_missing_columns_is_400(self, api_client):
        r = api_client.post("/predict/batch",
                            files={"file": ("d.csv", "a,b\n1,2\n", "text/csv")})
        assert r.status_code == 400 and "missing required columns" in r.json()["detail"]


class TestScheduler:
    def test_demo_has_no_double_bookings(self, seeded_client):
        j = seeded_client.get("/schedule/demo").json()
        assert j["stats"]["double_bookings_after"] == 0
        assert j["stats"]["raw_conflicts_before"] > 0

    def test_payload_scheduling(self, seeded_client):
        payload = [{"booking_id": "B1", "project_id": "PRJ_001",
                    "project_priority": "high", "resource_type": "crane",
                    "requested_start": "2026-03-01T08:00:00",
                    "requested_end": "2026-03-01T18:00:00"}]
        j = seeded_client.post("/schedule", json=payload).json()
        assert j["stats"]["assigned"] == 1

    def test_empty_payload_is_400(self, seeded_client):
        assert seeded_client.post("/schedule", json=[]).status_code == 400


class TestValidator:
    def test_demo_scores_against_ground_truth(self, seeded_client):
        j = seeded_client.get("/validate/demo").json()
        assert j["metrics_vs_ground_truth"]["recall"] == 1.0

    def test_payload_flags_premature(self, seeded_client):
        j = seeded_client.post("/validate", json=[{
            "project_id": "P1", "material_type": "cement",
            "required_phase": "foundation", "delivery_date": "2026-03-01",
            "phase_start_date": "2026-03-20", "phase_end_date": "2026-04-01"}]).json()
        assert j["deliveries"][0]["predicted_flag"] == "premature_delivery"


class TestPlatformView:
    def test_overview_returns_all_three_engines(self, seeded_client):
        j = seeded_client.get("/projects/PRJ_001/overview").json()
        assert {"delay_prediction", "resource_schedule", "sequencing"} <= set(j)
        assert j["project"]["project_id"] == "PRJ_001"

    def test_unknown_project_is_404(self, seeded_client):
        assert seeded_client.get("/projects/NOPE/overview").status_code == 404


class TestEvidenceLoop:
    def test_predictions_are_logged_then_scored(self, api_client):
        api_client.post("/predict", json={**SAMPLE, "supplier_id": "LOGGED_1"})
        logged = api_client.get("/predictions?limit=10").json()
        assert logged["count"] >= 1
        row = logged["predictions"][0]
        assert row["model_version"] and row["predicted_band"]

        # close the loop: an outcome 30 days late must score as late
        upd = api_client.post("/outcomes", json=[{
            "prediction_id": row["id"], "actual_date": "2026-06-20", "grace_days": 1}]).json()
        assert upd["updated"] == 1

        acc = api_client.get("/accuracy").json()
        assert acc["with_known_outcome"] >= 1
        assert 0.0 <= acc["accuracy"] <= 1.0

    def test_accuracy_is_honest_when_no_outcomes(self, api_client):
        j = api_client.get("/accuracy").json()
        assert j["with_known_outcome"] == 0
        assert "note" in j

    def test_outcome_without_identifier_is_reported(self, api_client):
        j = api_client.post("/outcomes", json=[{"actual_date": "2026-06-20"}]).json()
        assert j["updated"] == 0 and j["unmatched"]
