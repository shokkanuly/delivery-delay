"""Module 2 router — resource scheduling (/schedule)."""
from __future__ import annotations

import io

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile

from api.data_sources import read_reference
from engines.scheduler import count_raw_conflicts, solve_schedule
from engines.scheduler.solver import verify_no_double_booking

router = APIRouter(prefix="/schedule", tags=["scheduler"])

BOOKING_COLUMNS = ["booking_id", "project_id", "resource_type",
                   "requested_start", "requested_end"]

# How far before a booking a delivery can be and still strand it.
DEPENDENCY_WINDOW_DAYS = 14


def booking_risk_from_delay_engine(bookings: pd.DataFrame) -> dict[str, float]:
    """Engine 1 -> engine 2. The coupling that makes this a platform.

    A booking's risk is the highest delay risk among the deliveries it actually
    depends on: same project, promised inside a window around the booking. If the
    material a crane is booked for is likely to slip, that slot is likely to be
    wasted, so the scheduler prefers local (cheap to re-mobilise) resources.

    The window matters. Taking the max over *all* prior deliveries marks every
    booking high-risk, which is the same as marking none: the discount stops
    discriminating. Only deliveries due shortly before the slot (or during it)
    can actually strand it.

    Best-effort — if the model or its data is unavailable, scheduling proceeds
    exactly as before rather than failing.
    """
    try:
        from ml.predict import load_artifact, score

        deliveries = read_reference("delay_prediction.csv")
        needed = {"project_id", "supplier_id", "material_type", "route_type",
                  "quantity", "order_date", "promised_date"}
        if not needed <= set(deliveries.columns):
            return {}

        projects = set(bookings["project_id"].astype(str))
        rel = deliveries[deliveries["project_id"].astype(str).isin(projects)]
        if rel.empty:
            return {}

        scored = score(rel[["supplier_id", "material_type", "route_type", "quantity",
                            "order_date", "promised_date"]].to_dict("records"),
                       load_artifact())
        rel = rel.assign(risk=scored["risk"].to_numpy(),
                         promised=pd.to_datetime(rel["promised_date"]))

        risk: dict[str, float] = {}
        for _, b in bookings.iterrows():
            start = pd.Timestamp(b["requested_start"])
            end = pd.Timestamp(b["requested_end"])
            window = rel[(rel["project_id"].astype(str) == str(b["project_id"]))
                         & (rel["promised"] >= start - pd.Timedelta(days=DEPENDENCY_WINDOW_DAYS))
                         & (rel["promised"] <= end)]
            if len(window):
                risk[b["booking_id"]] = float(window["risk"].max())
        return risk
    except Exception:  # noqa: BLE001 - the scheduler must still run
        return {}


def _run(bookings: pd.DataFrame) -> dict:
    resources = read_reference("resources.csv")
    projects = read_reference("projects.csv")
    raw_conflicts = count_raw_conflicts(bookings)
    risk = booking_risk_from_delay_engine(bookings)
    result = solve_schedule(bookings, resources, projects, risk_by_booking=risk)
    clashes = verify_no_double_booking(result.assignments)
    return {
        "stats": {**result.stats,
                  "raw_conflicts_before": raw_conflicts,
                  "double_bookings_after": len(clashes),
                  "bookings_with_delay_risk": len(risk),
                  "high_risk_bookings": sum(v >= 0.66 for v in risk.values())},
        "assignments": result.assignments,
        "unassigned": result.unassigned,
    }


@router.post("")
def schedule_from_payload(bookings: list[dict]) -> dict:
    """Assign resources to a list of booking requests (JSON body)."""
    if not bookings:
        raise HTTPException(status_code=400, detail="No bookings supplied.")
    df = pd.DataFrame(bookings)
    missing = set(BOOKING_COLUMNS) - set(df.columns)
    if missing:
        raise HTTPException(status_code=400,
                            detail=f"bookings missing required fields: {sorted(missing)}")
    return _run(df)


@router.post("/upload")
def schedule_from_csv(file: UploadFile = File(...)) -> dict:
    """Assign resources for an uploaded booking_requests CSV."""
    try:
        df = pd.read_csv(io.BytesIO(file.file.read()))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {exc}")
    missing = set(BOOKING_COLUMNS) - set(df.columns)
    if missing:
        raise HTTPException(status_code=400,
                            detail=f"CSV missing required columns: {sorted(missing)}")
    return _run(df)


@router.get("/demo")
def schedule_demo(project_id: str | None = None) -> dict:
    """Solve the bundled synthetic booking set — the one-click demo path."""
    df = read_reference("booking_requests.csv")
    if project_id:
        df = df[df["project_id"] == project_id]
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No bookings for {project_id}")
    return _run(df)
