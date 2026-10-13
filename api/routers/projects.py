"""Platform router — the master project list and the one-site overview that
puts all three engines side by side (/projects, /projects/{id}/overview)."""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException

from api.model_store import get_artifact, prediction_fields
from ml.predict import score

router = APIRouter(tags=["projects"])


@router.get("/projects")
def list_projects() -> dict:
    """Master project list — shared by all three engines."""
    from api.data_sources import read_reference
    return {"projects": read_reference("projects.csv").to_dict("records")}


@router.get("/projects/{project_id}/overview")
def project_overview(project_id: str) -> dict:
    """All three engines for one project, side by side.

    This is the platform view: delay risk, resource conflicts and sequencing
    flags for a single site in one response -- one platform solving three cost
    problems, rather than three disconnected demos.
    """
    from api.data_sources import read_reference
    from api.routers.schedule import _run as run_schedule
    from api.routers.validate import _run as run_validate

    projects = read_reference("projects.csv")
    row = projects[projects["project_id"] == project_id]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"Unknown project {project_id}")

    # Engine 1 — delay risk on this project's deliveries
    deliveries = read_reference("delay_prediction.csv")
    d = deliveries[deliveries["project_id"] == project_id]
    delay_block: dict = {"scored": 0}
    if not d.empty:
        recs = d.rename(columns={"project_site": "site"})[
            ["supplier_id", "material_type", "route_type", "quantity",
             "order_date", "promised_date"]
        ].to_dict("records")
        scored = score(recs, get_artifact())
        merged = []
        for src, (_, s) in zip(d.to_dict("records"), scored.iterrows()):
            merged.append({"delivery_id": src["delivery_id"],
                           "supplier_id": src["supplier_id"],
                           "material_type": src["material_type"],
                           "promised_date": src["promised_date"],
                           **prediction_fields(s)})
        merged.sort(key=lambda x: x["risk"], reverse=True)
        bands = pd.Series([m["risk_band"] for m in merged]).value_counts().to_dict()
        delay_block = {"scored": len(merged), "bands": bands, "top_risks": merged[:10]}

    # Engine 2 — scheduling for this project's bookings
    bookings = read_reference("booking_requests.csv")
    pb = bookings[bookings["project_id"] == project_id]
    schedule_block = run_schedule(pb) if not pb.empty else {"stats": {}, "assignments": []}

    # Engine 3 — sequencing flags for this project
    md = read_reference("material_deliveries.csv")
    pm = md[md["project_id"] == project_id]
    validate_block = (run_validate(pm, read_reference("build_phases.csv"), score=True)
                      if not pm.empty else {"counts": {}, "deliveries": []})

    return {
        "project": row.iloc[0].to_dict(),
        "delay_prediction": delay_block,
        "resource_schedule": {"stats": schedule_block["stats"],
                              "assignments": schedule_block["assignments"][:20]},
        "sequencing": {"counts": validate_block["counts"],
                       "flagged": [r for r in validate_block["deliveries"]
                                   if r.get("predicted_flag")][:20]},
    }
