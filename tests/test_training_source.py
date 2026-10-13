"""App <-> ML boundary: the model must be trained on the data the DB is seeded
from. They once diverged (simulator vs CSV) and the served model knew 0 of the
10 suppliers it scored."""
from __future__ import annotations

import inspect

from db import seed
from ml import train


def test_seed_and_train_share_one_default_source():
    assert train.DEFAULT_TRAINING_CSV.resolve() == seed.DEFAULT_DELIVERIES.resolve()
    default = inspect.signature(train.fit_and_save).parameters["csv_path"].default
    assert default == str(train.DEFAULT_TRAINING_CSV)


def test_health_reports_coverage_and_source():
    from fastapi.testclient import TestClient
    from api.main import app
    body = TestClient(app).get("/health").json()
    assert "supplier_coverage" in body and "data_source" in body
