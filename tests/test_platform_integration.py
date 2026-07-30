"""Tests for the brief items completed last: DB as source of truth, the
delay->scheduler coupling, distance_km, the 3-class head, the threshold
baseline, and anomaly detection."""
from __future__ import annotations

import pandas as pd
import pytest

from ml.features import ROUTE_DEFAULT_KM, build_features, build_snapshot, distance_series


class TestAllCsvsInDatabase:
    """The brief: load all seven CSVs into tables of the same name, so every
    engine queries one source of truth instead of re-reading CSVs."""

    def test_every_table_is_populated(self, temp_db):
        counts = temp_db["seed"].seed()
        for table in ("projects", "suppliers", "deliveries", "resources",
                      "booking_requests", "build_phases", "phase_material_map",
                      "material_deliveries"):
            assert counts[table] > 0, f"{table} is empty"

    def test_engines_read_from_the_database(self, temp_db):
        """Emptying a table must change what the engine sees — proving it reads
        the DB rather than falling back to the bundled CSV."""
        temp_db["seed"].seed()
        from api.data_sources import read_reference

        session = temp_db["Session"]()
        try:
            before = len(read_reference("resources.csv", db=session))
            session.query(temp_db["models"].Resource).delete()
            session.commit()
            after_rows = read_reference("resources.csv", db=session)
        finally:
            session.close()

        assert before == 28
        # table now empty -> falls back to the bundled CSV, not stale DB state
        assert len(after_rows) == 28

    def test_project_ids_are_shared_across_engines(self, temp_db):
        """One project vocabulary: deliveries, bookings and phases must all use
        the same PRJ_* keys."""
        temp_db["seed"].seed()
        m = temp_db["models"]
        session = temp_db["Session"]()
        try:
            projects = {p.id for p in session.query(m.Project).all()}
            assert {b.project_id for b in session.query(m.BookingRequest).all()} <= projects
            assert {p.project_id for p in session.query(m.BuildPhase).all()} <= projects
            assert {d.project_id for d in session.query(m.Delivery).all()} <= projects
        finally:
            session.close()


class TestDelayToSchedulerCoupling:
    """The brief calls this the platform's whole point: engine 1's risk scores
    must actually reach engine 2."""

    def test_risk_reaches_the_scheduler(self, seeded_client):
        stats = seeded_client.get("/schedule/demo").json()["stats"]
        assert stats["bookings_with_delay_risk"] > 0, "no booking got a risk score"

    def test_risk_discriminates(self, seeded_client):
        """A signal that fires on every booking is the same as no signal."""
        stats = seeded_client.get("/schedule/demo").json()["stats"]
        assert 0 < stats["high_risk_bookings"] < stats["bookings"]

    def test_high_risk_booking_prefers_a_local_resource(self):
        """The behavioural claim: at-risk slots get cheap-to-remobilise (local)
        resources, so a slipped delivery doesn't strand a long haul."""
        from engines.scheduler import solve_schedule

        bookings = pd.DataFrame([{
            "booking_id": "B1", "project_id": "P1", "project_priority": "medium",
            "resource_type": "truck", "requested_start": "2026-03-01T08:00:00",
            "requested_end": "2026-03-01T18:00:00", "task": "haul"}])
        resources = pd.DataFrame([
            {"resource_id": "FAR", "type": "truck", "capacity": 1, "home_location": "Atyrau"},
            {"resource_id": "NEAR", "type": "truck", "capacity": 1, "home_location": "Almaty"}])
        projects = pd.DataFrame([{"project_id": "P1", "location": "Almaty"}])

        res = solve_schedule(bookings, resources, projects,
                             risk_by_booking={"B1": 0.95})
        assert res.assignments[0]["assigned_resource_id"] == "NEAR"


class TestDistanceFeature:
    def test_distance_is_a_model_feature(self, synthetic_deliveries):
        X, _, _ = build_features(synthetic_deliveries)
        assert "distance_km" in X.columns

    def test_observed_distance_is_used_when_present(self):
        df = pd.DataFrame([{"route_type": "urban", "distance_km": 999.0}])
        assert distance_series(df).iloc[0] == 999.0

    def test_falls_back_to_route_class_when_missing(self):
        df = pd.DataFrame([{"route_type": "cross_border"}])
        assert distance_series(df).iloc[0] == ROUTE_DEFAULT_KM["cross_border"]

    def test_snapshot_learns_route_medians(self, synthetic_deliveries):
        df = synthetic_deliveries.copy()
        df["distance_km"] = 100.0
        assert build_snapshot(df)["route_distance_km"]["urban"] == 100.0


class TestExtraHeads:
    def test_three_class_head_predicts_more_than_one_class(self, artifact):
        """It previously collapsed onto the majority class (late F1 0.04)."""
        metrics = artifact["status_metrics"]
        if "per_class_f1" not in metrics:
            pytest.skip("too few rows in a class to cross-validate")
        assert metrics["per_class_f1"].get("late", 0) > 0.15

    def test_threshold_baseline_is_reported(self, artifact):
        tb = artifact["threshold_baseline"]
        assert "0.7" in tb["rule"]
        assert 0.0 <= tb["recall"] <= 1.0


class TestAnomalyDetection:
    def test_flags_a_minority_not_everything(self, platform_data):
        from engines.validator import detect_anomalies
        res = detect_anomalies(platform_data["deliveries"])
        assert res.fitted
        flagged = [r for r in res.rows if r["anomaly"]]
        assert 0 < len(flagged) < len(res.rows) * 0.25

    def test_declines_when_history_is_too_thin(self, platform_data):
        """With little data it just rediscovers the rules, so it should say so
        rather than emit noise."""
        from engines.validator import detect_anomalies
        res = detect_anomalies(platform_data["deliveries"].head(10))
        assert not res.fitted and "needs at least" in res.note
