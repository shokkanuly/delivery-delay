"""Shared fixtures.

Tests run against an isolated temp SQLite file and a small model trained once
per session, so they never touch the developer's delivery.db or ml/artifacts/.
"""
from __future__ import annotations

import pathlib
import tempfile

import pandas as pd
import pytest

DATA = pathlib.Path(__file__).resolve().parent.parent / "data" / "synthetic"


@pytest.fixture(scope="session")
def synthetic_deliveries() -> pd.DataFrame:
    from ml.data_sim import generate_deliveries
    from ml.labeling import LabelConfig, add_labels
    return add_labels(generate_deliveries(n=400, seed=3), LabelConfig())


@pytest.fixture(scope="session")
def platform_data() -> dict:
    """The bundled platform CSVs (skip cleanly if they aren't present)."""
    if not (DATA / "booking_requests.csv").exists():
        pytest.skip("data/synthetic not present")
    return {
        "bookings": pd.read_csv(DATA / "booking_requests.csv"),
        "resources": pd.read_csv(DATA / "resources.csv"),
        "projects": pd.read_csv(DATA / "projects.csv"),
        "deliveries": pd.read_csv(DATA / "material_deliveries.csv"),
        "phases": pd.read_csv(DATA / "build_phases.csv"),
        "phase_map": DATA / "phase_material_map.csv",
    }


@pytest.fixture(scope="session")
def artifact(synthetic_deliveries):
    """A small model artifact trained into a temp dir (never the real one)."""
    from ml.train import fit_and_save
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "m.joblib"
        art, _ = fit_and_save(path=path, n=400, seed=3)
        yield art


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """Point the app at a throwaway SQLite file.

    Rebinds the engine/session on the already-imported modules rather than
    reloading them: re-importing the SQLAlchemy models would re-register every
    table on the same MetaData and blow up with "table already defined".
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import db.database as database
    import db.models as models  # noqa: F401  (registers mappers)
    import db.seed as seed_mod

    engine = create_engine(f"sqlite:///{tmp_path}/test.db", future=True,
                           connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    # get_session() reads these module globals at call time, so patching them
    # redirects the API too. db.seed imported the names, so patch it as well.
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", Session)
    monkeypatch.setattr(seed_mod, "engine", engine)
    monkeypatch.setattr(seed_mod, "SessionLocal", Session)

    database.Base.metadata.create_all(bind=engine)
    return {"database": database, "models": models, "seed": seed_mod,
            "engine": engine, "Session": Session}


@pytest.fixture()
def seeded_client(temp_db):
    """API client against a DB seeded with the full platform data set."""
    temp_db["seed"].seed()
    from fastapi.testclient import TestClient

    import api.main as main
    with TestClient(main.app) as client:
        yield client


@pytest.fixture()
def api_client(temp_db):
    """TestClient backed by the throwaway DB."""
    from fastapi.testclient import TestClient

    import api.main as main
    with TestClient(main.app) as client:
        yield client
