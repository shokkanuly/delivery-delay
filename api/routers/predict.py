"""Module 1 router — delay prediction and model operations
(/health, /metrics, /train, /predict, /predict/batch, /deliveries/{project_id})."""
from __future__ import annotations

import io

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from api.model_store import get_artifact, log_safely, prediction_fields, supplier_coverage
from api.schemas import DeliveryIn, PredictionOut
from api.security import require_admin
from db.database import get_session
from db.models import Delivery
from ml.predict import REQUIRED_FIELDS, score
from ml.train import fit_and_save

router = APIRouter(tags=["delay prediction"])


@router.get("/health")
def health() -> dict:
    art = get_artifact()
    return {"status": "ok", "trained_rows": art["trained_rows"],
            "data_source": art.get("data_source", "unknown"),
            "supplier_coverage": supplier_coverage(art),
            "n_features": len(art["feature_columns"]),
            "engines": ["delay_prediction", "resource_scheduler", "sequence_validator"]}


@router.get("/metrics")
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


@router.post("/train", dependencies=[Depends(require_admin)])
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


@router.post("/predict", response_model=PredictionOut)
def predict_one(delivery: DeliveryIn, db: Session = Depends(get_session)) -> dict:
    rec = delivery.model_dump()
    scored = score([rec], get_artifact())
    log_safely(db, [rec], scored)
    return prediction_fields(scored.iloc[0])


@router.post("/predict/batch")
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
    log_safely(db, records, scored)
    rows = []
    for src, (_, s) in zip(records, scored.iterrows()):
        rows.append({**src, **prediction_fields(s)})
    rows.sort(key=lambda r: r["risk"], reverse=True)
    return {"count": len(rows), "rows": rows}


@router.get("/deliveries/{project_id}")
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
            **prediction_fields(s),
        })
    out.sort(key=lambda x: x["risk"], reverse=True)
    return {"project_id": project_id, "count": len(out), "deliveries": out}
