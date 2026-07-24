"""Populate the database with synthetic deliveries for the demo.

Destructive by design: it drops and recreates the tables (it owns the dev DB).
When real BI Group data arrives, replace `generate_deliveries(...)` with your CSV
/ ETL load -- the rest is unchanged.
"""
from __future__ import annotations

import pandas as pd

from db.database import Base, SessionLocal, engine, init_db
from db.models import Delivery, Project, Supplier
from ml.data_sim import generate_deliveries
from ml.labeling import LabelConfig, add_labels


def _supplier_rollups(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("supplier_id")
    return pd.DataFrame(
        {
            "avg_delay_days": g["delay_days"].mean(),
            "on_time_rate": 1.0 - g["is_late"].mean(),
            "material_types": g["material_type"].agg(lambda s: sorted(s.unique().tolist())),
        }
    )


def seed(n: int = 1200, seed_val: int = 7, csv_path: str | None = None) -> dict:
    Base.metadata.drop_all(bind=engine)
    init_db()
    if csv_path:
        from ml.ingest import load_deliveries_csv
        df = add_labels(load_deliveries_csv(csv_path, require_actual=True), LabelConfig())
    else:
        df = add_labels(generate_deliveries(n=n, seed=seed_val), LabelConfig())

    session = SessionLocal()
    try:
        # one project per distinct site
        sites = sorted(df["project_site"].unique())
        proj_id = {site: i for i, site in enumerate(sites, start=1)}
        for site, pid in proj_id.items():
            session.add(Project(
                id=pid, name=site.replace("_", " ").title(), location=site,
                start_date=df["order_date"].min().date(),
                end_date=df["actual_date"].max().date(),
            ))

        # suppliers with display-only rollups
        for sid, r in _supplier_rollups(df).iterrows():
            session.add(Supplier(
                id=sid, name=f"Supplier {sid}",
                avg_delay_days=float(r["avg_delay_days"]),
                on_time_rate=float(r["on_time_rate"]),
                material_types=list(r["material_types"]),
            ))

        # deliveries (all synthetic rows are delivered, so status is known)
        for _, d in df.iterrows():
            session.add(Delivery(
                id=int(d["delivery_id"]),
                supplier_id=d["supplier_id"],
                project_id=proj_id[d["project_site"]],
                material_type=d["material_type"],
                route_type=d["route_type"],
                quantity=int(d["quantity"]),
                order_date=d["order_date"].date(),
                promised_date=d["promised_date"].date(),
                actual_date=d["actual_date"].date(),
                status="late" if d["is_late"] else "on_time",
            ))

        session.commit()
        return {
            "suppliers": session.query(Supplier).count(),
            "projects": session.query(Project).count(),
            "deliveries": session.query(Delivery).count(),
        }
    finally:
        session.close()


if __name__ == "__main__":
    import sys

    csv = sys.argv[1] if len(sys.argv) > 1 else None
    print("seeded:", seed(csv_path=csv))
