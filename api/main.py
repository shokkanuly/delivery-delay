"""BI Group delivery-delay API.

Endpoints (from the plan):
  GET  /health                     liveness + model info
  GET  /metrics                    CV model-vs-baseline scorecard
  POST /predict                    score a single delivery
  POST /predict/batch              score an uploaded CSV
  GET  /deliveries/{project_id}    list a project's deliveries, risk-sorted

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

from api.schemas import DeliveryIn, PredictionOut
from db.database import get_session
from db.models import Delivery
from ml.predict import REQUIRED_FIELDS, load_artifact, score
from ml.train import ARTIFACT_PATH, fit_and_save

app = FastAPI(title="BI Group Delivery-Delay API", version="0.1.0")


@lru_cache
def get_artifact() -> dict:
    """Load the model artifact once; train one on first use if none exists."""
    if not ARTIFACT_PATH.exists():
        fit_and_save()
    return load_artifact()


def _prediction_fields(row: pd.Series) -> dict:
    return {
        "risk": float(row["risk"]),
        "risk_band": str(row["risk_band"]),
        "supplier_late_rate": float(row["supplier_late_rate"]),
        "supplier_n_prior": int(row["supplier_n_prior"]),
        "lead_time_days": int(row["lead_time_days"]),
        "drivers": row["drivers"],
    }


@app.get("/health")
def health() -> dict:
    art = get_artifact()
    return {"status": "ok", "trained_rows": art["trained_rows"],
            "n_features": len(art["feature_columns"])}


@app.get("/metrics")
def metrics() -> dict:
    """Cross-validated model-vs-baseline scorecard (for the dashboard header)."""
    return get_artifact()["metrics"]


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
def predict_one(delivery: DeliveryIn) -> dict:
    scored = score([delivery.model_dump()], get_artifact())
    return _prediction_fields(scored.iloc[0])


@app.post("/predict/batch")
def predict_batch(file: UploadFile = File(...)) -> dict:
    try:
        raw = pd.read_csv(io.BytesIO(file.file.read()))
    except Exception as exc:  # noqa: BLE001 - surface any parse error to the client
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {exc}")

    missing = set(REQUIRED_FIELDS) - set(raw.columns)
    if missing:
        raise HTTPException(status_code=400,
                            detail=f"CSV missing required columns: {sorted(missing)}")

    scored = score(raw, get_artifact())
    rows = []
    for src, (_, s) in zip(raw.to_dict("records"), scored.iterrows()):
        rows.append({**src, **_prediction_fields(s)})
    rows.sort(key=lambda r: r["risk"], reverse=True)
    return {"count": len(rows), "rows": rows}


@app.get("/deliveries/{project_id}")
def deliveries_for_project(project_id: int, limit: int = 500,
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
