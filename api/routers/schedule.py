"""Module 2 router — resource scheduling (/schedule)."""
from __future__ import annotations

import io

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile

from api.data_sources import SYNTHETIC_DIR, read_synthetic
from engines.scheduler import count_raw_conflicts, solve_schedule
from engines.scheduler.solver import verify_no_double_booking

router = APIRouter(prefix="/schedule", tags=["scheduler"])

BOOKING_COLUMNS = ["booking_id", "project_id", "resource_type",
                   "requested_start", "requested_end"]


def _run(bookings: pd.DataFrame) -> dict:
    resources = read_synthetic("resources.csv")
    projects = read_synthetic("projects.csv")
    raw_conflicts = count_raw_conflicts(bookings)
    result = solve_schedule(bookings, resources, projects)
    clashes = verify_no_double_booking(result.assignments)
    return {
        "stats": {**result.stats,
                  "raw_conflicts_before": raw_conflicts,
                  "double_bookings_after": len(clashes)},
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
    if not (SYNTHETIC_DIR / "booking_requests.csv").exists():
        raise HTTPException(status_code=404, detail="Synthetic booking data not found.")
    df = read_synthetic("booking_requests.csv")
    if project_id:
        df = df[df["project_id"] == project_id]
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No bookings for {project_id}")
    return _run(df)
