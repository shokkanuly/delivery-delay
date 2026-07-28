"""Regression tests for two bugs that reached the repo unnoticed.

Both were found by re-running the pipeline by hand, not by any check -- which is
precisely why they are pinned here.
"""
from __future__ import annotations

import pytest

CSV = ("supplier_id,project_site,material_type,route_type,quantity,"
       "order_date,promised_date,actual_date\n"
       "SUP_001,almaty,cement,urban,10,2026-01-01,2026-01-10,2026-01-12\n"
       "SUP_002,astana,rebar,intercity,20,2026-01-02,2026-01-12,2026-01-12\n")


@pytest.fixture()
def seeded_env(temp_db, tmp_path):
    """Throwaway DB plus a real-shaped deliveries CSV."""
    csv_path = tmp_path / "deliveries.csv"
    csv_path.write_text(CSV)
    return temp_db["seed"], temp_db["database"], temp_db["models"], str(csv_path)


def test_seed_from_csv_without_delivery_id_column(seeded_env):
    """ml.ingest normalises real CSVs and drops `delivery_id`; seeding must not
    assume it exists. Previously raised KeyError: 'delivery_id' -- on exactly the
    path real customer data takes."""
    seed_mod, _, _, csv_path = seeded_env
    counts = seed_mod.seed(csv_path=csv_path)
    assert counts["deliveries"] == 2
    assert counts["suppliers"] == 2


def test_reseeding_preserves_prediction_log(seeded_env):
    """Re-seeding reference data must never destroy the served-prediction record:
    it is the evidence that the model works. Previously drop_all() wiped it."""
    seed_mod, database, models, csv_path = seeded_env
    seed_mod.seed(csv_path=csv_path)

    session = database.SessionLocal()
    session.add(models.PredictionLog(
        model_version="v-test", supplier_id="SUP_001",
        predicted_risk=0.9, predicted_band="red", predicted_late=1))
    session.commit()
    session.close()

    seed_mod.seed(csv_path=csv_path)          # reseed again

    session = database.SessionLocal()
    surviving = session.query(models.PredictionLog).count()
    deliveries = session.query(models.Delivery).count()
    session.close()

    assert surviving == 1, "prediction_log was destroyed by re-seeding"
    assert deliveries == 2, "master data should still be refreshed"


def test_seeded_suppliers_match_trained_vocabulary(seeded_env):
    """The DB and the model must share a supplier vocabulary. When they drifted
    apart, every dashboard row silently fell back to cold-start."""
    seed_mod, database, models, csv_path = seeded_env
    seed_mod.seed(csv_path=csv_path)

    from ml.features import build_snapshot
    from ml.ingest import load_deliveries_csv
    from ml.labeling import add_labels

    snapshot = build_snapshot(add_labels(load_deliveries_csv(csv_path)))

    session = database.SessionLocal()
    db_suppliers = {s.id for s in session.query(models.Supplier).all()}
    session.close()

    assert db_suppliers <= set(snapshot["supplier"]), (
        "suppliers in the DB are unknown to the model -> silent cold-start")
