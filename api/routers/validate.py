"""Module 3 router — sequencing validation (/validate)."""
from __future__ import annotations

import io

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile

from api.data_sources import SYNTHETIC_DIR, read_synthetic
from engines.validator import (
    evaluate_against_truth,
    load_phase_material_map,
    validate_deliveries,
)
from engines.validator.rules import REQUIRED_COLUMNS

router = APIRouter(prefix="/validate", tags=["validator"])


def _phase_map():
    return load_phase_material_map(read_synthetic("phase_material_map.csv"))


def _run(deliveries: pd.DataFrame, build_phases: pd.DataFrame | None,
         score: bool) -> dict:
    summary = validate_deliveries(deliveries, phase_map=_phase_map(),
                                  build_phases=build_phases)
    out = {"counts": summary.counts, "deliveries": summary.rows}
    if score and "flag" in deliveries.columns:
        out["metrics_vs_ground_truth"] = evaluate_against_truth(summary)
    return out


@router.post("")
def validate_payload(deliveries: list[dict]) -> dict:
    """Validate a list of deliveries against the build programme."""
    if not deliveries:
        raise HTTPException(status_code=400, detail="No deliveries supplied.")
    df = pd.DataFrame(deliveries)
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise HTTPException(status_code=400,
                            detail=f"deliveries missing required fields: {sorted(missing)}")
    bp = read_synthetic("build_phases.csv") if (
        SYNTHETIC_DIR / "build_phases.csv").exists() else None
    return _run(df, bp, score=True)


@router.post("/upload")
def validate_csv(file: UploadFile = File(...)) -> dict:
    """Validate an uploaded material_deliveries CSV."""
    try:
        df = pd.read_csv(io.BytesIO(file.file.read()))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {exc}")
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise HTTPException(status_code=400,
                            detail=f"CSV missing required columns: {sorted(missing)}")
    bp = read_synthetic("build_phases.csv") if (
        SYNTHETIC_DIR / "build_phases.csv").exists() else None
    return _run(df, bp, score=True)


@router.get("/demo")
def validate_demo(project_id: str | None = None) -> dict:
    """Validate the bundled synthetic deliveries, scored against ground truth."""
    if not (SYNTHETIC_DIR / "material_deliveries.csv").exists():
        raise HTTPException(status_code=404, detail="Synthetic sequencing data not found.")
    df = read_synthetic("material_deliveries.csv")
    if project_id:
        df = df[df["project_id"] == project_id]
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No deliveries for {project_id}")
    return _run(df, read_synthetic("build_phases.csv"), score=True)
