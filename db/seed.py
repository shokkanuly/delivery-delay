"""Load every source CSV into the database.

The database is the single source of truth: all three engines query it rather
than re-reading CSVs at runtime, so one master project/supplier/material set
feeds delay prediction, scheduling and sequencing alike.

    python3 -m db.seed                                   # bundled platform data
    python3 -m db.seed path/to/deliveries.csv            # real deliveries

Destructive for the master tables it owns. `prediction_log` is PRESERVED: it is
the record of predictions actually served and scored against reality, and
re-seeding reference data must never destroy that evidence.
"""
from __future__ import annotations

import json

import pathlib

import pandas as pd

from db.database import Base, SessionLocal, engine, init_db
from db.models import (
    BookingRequest,
    BuildPhase,
    Delivery,
    MaterialDelivery,
    PhaseMaterialMap,
    Project,
    Resource,
    Supplier,
    Workspace,
)
from ml.data_sim import generate_deliveries
from ml.labeling import LabelConfig, add_labels

SYNTHETIC_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "synthetic"
DEFAULT_DELIVERIES = SYNTHETIC_DIR / "delay_prediction.csv"
DEMO_WORKSPACES = SYNTHETIC_DIR / "demo_workspaces.json"

OWNED_TABLES = [Delivery, MaterialDelivery, BookingRequest, BuildPhase,
                PhaseMaterialMap, Resource, Supplier, Project]


def _supplier_rollups(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("supplier_id")
    return pd.DataFrame(
        {
            "avg_delay_days": g["delay_days"].mean(),
            "on_time_rate": 1.0 - g["is_late"].mean(),
            "material_types": g["material_type"].agg(lambda s: sorted(s.unique().tolist())),
        }
    )


def _read(name: str) -> pd.DataFrame | None:
    path = SYNTHETIC_DIR / name
    return pd.read_csv(path) if path.exists() else None


def _load_deliveries(csv_path: str | None, n: int, seed_val: int) -> pd.DataFrame:
    if csv_path is None and DEFAULT_DELIVERIES.exists():
        csv_path = str(DEFAULT_DELIVERIES)
    if csv_path:
        from ml.ingest import load_deliveries_csv
        raw = pd.read_csv(csv_path)
        df = load_deliveries_csv(csv_path, require_actual=True)
        # ml.ingest normalises to canonical columns; carry project_id back so
        # deliveries join to the same projects the other engines use.
        if "project_id" in raw.columns and len(raw) == len(df):
            df["project_id"] = raw["project_id"].to_numpy()
        return add_labels(df, LabelConfig())
    return add_labels(generate_deliveries(n=n, seed=seed_val), LabelConfig())


def seed(n: int = 1200, seed_val: int = 7, csv_path: str | None = None) -> dict:
    Base.metadata.drop_all(bind=engine, tables=[m.__table__ for m in OWNED_TABLES])
    init_db()
    df = _load_deliveries(csv_path, n, seed_val)

    session = SessionLocal()
    try:
        # ---- projects: prefer the master CSV, else derive from delivery sites
        projects_csv = _read("projects.csv")
        if projects_csv is not None:
            for _, p in projects_csv.iterrows():
                session.add(Project(
                    id=str(p["project_id"]), name=p["name"], location=p.get("location"),
                    priority=p.get("priority"),
                    start_date=pd.to_datetime(p["start_date"]).date(),
                    end_date=pd.to_datetime(p["end_date"]).date(),
                ))
            known_projects = set(projects_csv["project_id"].astype(str))
        else:
            known_projects = set()

        if "project_id" not in df.columns:
            df["project_id"] = df["project_site"].map(
                lambda s: f"SITE_{str(s).upper()}")
        df["project_id"] = df["project_id"].astype(str)

        # any project referenced by a delivery but absent from the master list
        for pid in sorted(set(df["project_id"]) - known_projects):
            rows = df[df["project_id"] == pid]
            session.add(Project(
                id=pid, name=str(rows["project_site"].iloc[0]).replace("_", " ").title(),
                location=str(rows["project_site"].iloc[0]),
                start_date=rows["order_date"].min().date(),
                end_date=rows["actual_date"].max().date(),
            ))
        session.flush()

        # ---- suppliers (display-only rollups; the model recomputes causally)
        for sid, r in _supplier_rollups(df).iterrows():
            session.add(Supplier(
                id=sid, name=f"Supplier {sid}",
                avg_delay_days=float(r["avg_delay_days"]),
                on_time_rate=float(r["on_time_rate"]),
                material_types=list(r["material_types"]),
            ))

        # ---- deliveries
        for i, (_, d) in enumerate(df.iterrows(), start=1):
            session.add(Delivery(
                id=int(d["delivery_id"]) if "delivery_id" in df.columns else i,
                supplier_id=d["supplier_id"], project_id=d["project_id"],
                material_type=d["material_type"], route_type=d["route_type"],
                quantity=int(d["quantity"]),
                distance_km=(float(d["distance_km"])
                             if "distance_km" in df.columns and pd.notna(d["distance_km"])
                             else None),
                order_date=d["order_date"].date(),
                promised_date=d["promised_date"].date(),
                actual_date=d["actual_date"].date(),
                status="late" if d["is_late"] else "on_time",
            ))

        # ---- engine 2 master data
        resources = _read("resources.csv")
        if resources is not None:
            for _, r in resources.iterrows():
                session.add(Resource(
                    id=r["resource_id"], type=r["type"],
                    capacity=int(r["capacity"]), home_location=r["home_location"]))

        bookings = _read("booking_requests.csv")
        if bookings is not None:
            for _, b in bookings.iterrows():
                session.add(BookingRequest(
                    id=b["booking_id"], project_id=str(b["project_id"]),
                    project_priority=b.get("project_priority"),
                    resource_type=b["resource_type"],
                    requested_start=pd.to_datetime(b["requested_start"]),
                    requested_end=pd.to_datetime(b["requested_end"]),
                    task=b.get("task"),
                    assigned_resource_id=(b["assigned_resource_id"]
                                          if pd.notna(b.get("assigned_resource_id"))
                                          else None)))

        # ---- engine 3 master data
        phases = _read("build_phases.csv")
        if phases is not None:
            for _, p in phases.iterrows():
                session.add(BuildPhase(
                    project_id=str(p["project_id"]), phase_name=p["phase_name"],
                    phase_order=int(p["phase_order"]),
                    start_date=pd.to_datetime(p["start_date"]).date(),
                    end_date=pd.to_datetime(p["end_date"]).date()))

        pmap = _read("phase_material_map.csv")
        if pmap is not None:
            for _, p in pmap.iterrows():
                session.add(PhaseMaterialMap(
                    phase_name=p["phase_name"],
                    required_materials=(None if pd.isna(p["required_materials"])
                                        else str(p["required_materials"]))))

        mdel = _read("material_deliveries.csv")
        if mdel is not None:
            for _, m in mdel.iterrows():
                session.add(MaterialDelivery(
                    id=m["delivery_seq_id"], project_id=str(m["project_id"]),
                    material_type=m["material_type"], required_phase=m["required_phase"],
                    delivery_date=pd.to_datetime(m["delivery_date"]).date(),
                    phase_start_date=pd.to_datetime(m["phase_start_date"]).date(),
                    phase_end_date=pd.to_datetime(m["phase_end_date"]).date(),
                    flag=(None if pd.isna(m.get("flag")) else m["flag"])))

        # ---- demo workspaces: upserted read-only, never dropped, so reseeding
        # keeps any workspace a real company created.
        for key, entry in json.loads(DEMO_WORKSPACES.read_text()).items():
            inputs = {k: v for k, v in entry.items() if k not in ("access_key", "created_at")}
            session.merge(Workspace(access_key=key, inputs=inputs, read_only=True))

        session.commit()
        return {
            "demo_workspaces": session.query(Workspace).filter_by(read_only=True).count(),
            "projects": session.query(Project).count(),
            "suppliers": session.query(Supplier).count(),
            "deliveries": session.query(Delivery).count(),
            "resources": session.query(Resource).count(),
            "booking_requests": session.query(BookingRequest).count(),
            "build_phases": session.query(BuildPhase).count(),
            "phase_material_map": session.query(PhaseMaterialMap).count(),
            "material_deliveries": session.query(MaterialDelivery).count(),
        }
    finally:
        session.close()


if __name__ == "__main__":
    import sys

    csv = sys.argv[1] if len(sys.argv) > 1 else None
    print("seeded:", seed(csv_path=csv))
