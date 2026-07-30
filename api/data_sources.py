"""Master data access — the database is the source of truth.

All three engines read reference data through here, so one project/supplier/
material set feeds delay prediction, scheduling and sequencing alike rather than
each engine re-reading CSVs at runtime.

`read_reference` returns the same column names the engines already expect, so
engine code is unchanged whether a row came from Postgres, SQLite, or (only when
the tables are empty, e.g. a fresh checkout before seeding) the bundled CSVs.
"""
from __future__ import annotations

import pathlib

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.database import SessionLocal
from db.models import (
    BookingRequest,
    BuildPhase,
    MaterialDelivery,
    PhaseMaterialMap,
    Project,
    Resource,
)

SYNTHETIC_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "synthetic"


def _rows(db: Session, model, columns: dict) -> pd.DataFrame:
    """Select a model into a DataFrame using the engines' column names."""
    records = db.execute(select(model)).scalars().all()
    return pd.DataFrame(
        [{out: getattr(r, attr) for out, attr in columns.items()} for r in records]
    )


_MAPPING = {
    "resources.csv": (Resource, {
        "resource_id": "id", "type": "type", "capacity": "capacity",
        "home_location": "home_location"}),
    "projects.csv": (Project, {
        "project_id": "id", "name": "name", "location": "location",
        "priority": "priority", "start_date": "start_date", "end_date": "end_date"}),
    "booking_requests.csv": (BookingRequest, {
        "booking_id": "id", "project_id": "project_id",
        "project_priority": "project_priority", "resource_type": "resource_type",
        "requested_start": "requested_start", "requested_end": "requested_end",
        "task": "task", "assigned_resource_id": "assigned_resource_id"}),
    "build_phases.csv": (BuildPhase, {
        "project_id": "project_id", "phase_name": "phase_name",
        "phase_order": "phase_order", "start_date": "start_date",
        "end_date": "end_date"}),
    "phase_material_map.csv": (PhaseMaterialMap, {
        "phase_name": "phase_name", "required_materials": "required_materials"}),
    "material_deliveries.csv": (MaterialDelivery, {
        "delivery_seq_id": "id", "project_id": "project_id",
        "material_type": "material_type", "required_phase": "required_phase",
        "delivery_date": "delivery_date", "phase_start_date": "phase_start_date",
        "phase_end_date": "phase_end_date", "flag": "flag"}),
}


def read_reference(name: str, db: Session | None = None) -> pd.DataFrame:
    """Master data for `name` (a CSV filename, kept as the stable key).

    Reads the database first and falls back to the bundled CSV only when the
    table is empty -- so a fresh checkout still works before `python3 -m db.seed`.
    """
    mapping = _MAPPING.get(name)
    if mapping is not None:
        model, columns = mapping
        own_session = db is None
        session = db or SessionLocal()
        try:
            df = _rows(session, model, columns)
        finally:
            if own_session:
                session.close()
        if not df.empty:
            return df

    path = SYNTHETIC_DIR / name
    if path.exists():
        return pd.read_csv(path)
    raise FileNotFoundError(f"No data for {name} in the database or {SYNTHETIC_DIR}")


# Back-compat alias: engines and routers call this name.
read_synthetic = read_reference
