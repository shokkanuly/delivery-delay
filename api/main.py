"""Construction Logistics Platform API — one service, three engines.

  Engine 1 · delay prediction   /predict, /predict/batch, /deliveries/{id}, /train
  Engine 2 · resource scheduler /schedule            (api/routers/schedule.py)
  Engine 3 · sequence validator /validate            (api/routers/validate.py)
  Platform                      /health, /metrics, /projects/{id}/overview

The trained artifact is loaded once and cached. Scoring is stateless -- it reads
the frozen feature snapshot inside the artifact (see ROADMAP), so no per-request
recomputation of causal history is needed.
"""
from __future__ import annotations

import io
from functools import lru_cache

import pandas as pd
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from api.routers import monitoring as monitoring_router
from api.routers import schedule as schedule_router
from api.routers import validate as validate_router
from api.routers.monitoring import log_predictions
from api.schemas import DeliveryIn, PredictionOut
from db.database import get_session
from db.models import Delivery
from ml.predict import REQUIRED_FIELDS, load_artifact, score
from ml.train import ARTIFACT_PATH, fit_and_save

app = FastAPI(
    title="Construction Logistics Platform",
    description="Delay prediction · resource scheduling · sequencing validation",
    version="0.2.0",
)

app.include_router(schedule_router.router)
app.include_router(validate_router.router)
app.include_router(monitoring_router.router)


def _log_safely(db: Session, records: list[dict], scored: pd.DataFrame) -> None:
    """Record served predictions for later scoring against reality.

    Best-effort by design: an audit-log failure must never take down scoring.
    """
    try:
        log_predictions(db, records, scored, get_artifact().get("model_version", "unknown"))
    except Exception:  # noqa: BLE001
        db.rollback()


@lru_cache
def get_artifact() -> dict:
    """Load the model artifact once; train one on first use if none exists."""
    if not ARTIFACT_PATH.exists():
        fit_and_save()
    return load_artifact()


def _prediction_fields(row: pd.Series) -> dict:
    delay = row.get("expected_delay_days")
    return {
        "risk": float(row["risk"]),
        "risk_band": str(row["risk_band"]),
        "supplier_late_rate": float(row["supplier_late_rate"]),
        "supplier_n_prior": int(row["supplier_n_prior"]),
        "lead_time_days": int(row["lead_time_days"]),
        "expected_delay_days": (None if delay is None or pd.isna(delay) else float(delay)),
        "drivers": row["drivers"],
    }


@app.get("/health")
def health() -> dict:
    art = get_artifact()
    return {"status": "ok", "trained_rows": art["trained_rows"],
            "n_features": len(art["feature_columns"]),
            "engines": ["delay_prediction", "resource_scheduler", "sequence_validator"]}


@app.get("/projects")
def list_projects() -> dict:
    """Master project list — shared by all three engines."""
    from api.data_sources import read_reference
    return {"projects": read_reference("projects.csv").to_dict("records")}


@app.get("/projects/{project_id}/overview")
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
                           **_prediction_fields(s)})
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


@app.get("/metrics")
def metrics() -> dict:
    """Cross-validated model-vs-baseline scorecard (for the dashboard header).

    `delay_days_head` carries its own `beats_baseline` flag: on the current data
    the expected-delay regressor does NOT beat predicting the mean, so consumers
    should present that number with a caveat rather than as a firm estimate.
    """
    art = get_artifact()
    return {**art["metrics"],
            "delay_days_head": art.get("delay_metrics", {}),
            "status_head": art.get("status_metrics", {}),
            "threshold_baseline": art.get("threshold_baseline", {}),
            "model_version": art.get("model_version")}


@app.post("/train")
def train() -> dict:
    """Retrain on the current data source and hot-swap the served model.

    Synchronous (training takes seconds at MVP scale). Clears the cached artifact
    so subsequent requests use the fresh model.
    """
    fit_and_save()
    get_artifact.cache_clear()
    art = get_artifact()
    return {"status": "retrained", "trained_rows": art["trained_rows"],
            "metrics": art["metrics"]}


@app.post("/predict", response_model=PredictionOut)
def predict_one(delivery: DeliveryIn, db: Session = Depends(get_session)) -> dict:
    rec = delivery.model_dump()
    scored = score([rec], get_artifact())
    _log_safely(db, [rec], scored)
    return _prediction_fields(scored.iloc[0])


@app.post("/predict/batch")
def predict_batch(file: UploadFile = File(...),
                  db: Session = Depends(get_session)) -> dict:
    try:
        raw = pd.read_csv(io.BytesIO(file.file.read()))
    except Exception as exc:  # noqa: BLE001 - surface any parse error to the client
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {exc}")

    missing = set(REQUIRED_FIELDS) - set(raw.columns)
    if missing:
        raise HTTPException(status_code=400,
                            detail=f"CSV missing required columns: {sorted(missing)}")

    scored = score(raw, get_artifact())
    records = raw.to_dict("records")
    _log_safely(db, records, scored)
    rows = []
    for src, (_, s) in zip(records, scored.iterrows()):
        rows.append({**src, **_prediction_fields(s)})
    rows.sort(key=lambda r: r["risk"], reverse=True)
    return {"count": len(rows), "rows": rows}


@app.get("/deliveries/{project_id}")
def deliveries_for_project(project_id: str, limit: int = 500,
                           db: Session = Depends(get_session)) -> dict:
    rows = (db.query(Delivery)
              .filter(Delivery.project_id == project_id)
              .limit(limit).all())
    if not rows:
        raise HTTPException(status_code=404,
                            detail=f"No deliveries for project {project_id}")

    records = [
        {"supplier_id": r.supplier_id, "material_type": r.material_type,
         "route_type": r.route_type, "quantity": r.quantity,
         "order_date": r.order_date, "promised_date": r.promised_date}
        for r in rows
    ]
    scored = score(records, get_artifact())

    out = []
    for r, (_, s) in zip(rows, scored.iterrows()):
        out.append({
            "delivery_id": r.id,
            "supplier_id": r.supplier_id,
            "material_type": r.material_type,
            "route_type": r.route_type,
            "quantity": r.quantity,
            "order_date": r.order_date,
            "promised_date": r.promised_date,
            "actual_date": r.actual_date,   # historical outcome, for predicted-vs-actual
            "status": r.status,
            **_prediction_fields(s),
        })
    out.sort(key=lambda x: x["risk"], reverse=True)
    return {"project_id": project_id, "count": len(out), "deliveries": out}
