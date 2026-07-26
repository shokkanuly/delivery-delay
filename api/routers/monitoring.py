"""Prediction logging, outcome capture, and realized accuracy.

The loop that turns a demo into evidence:

    /predict  ->  prediction_log row (what we said, and when)
    /outcomes ->  fill in what actually happened
    /accuracy ->  score served predictions against reality

Cross-validated metrics argue the model *should* work. Realized accuracy on
predictions actually served is what convinces a sceptical judge or client, and
it is the only metric that keeps being true after the data drifts.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from db.database import get_session
from db.models import PredictionLog

router = APIRouter(tags=["monitoring"])

LATE_DECISION_THRESHOLD = 0.5


def log_predictions(db: Session, records: list[dict], scored: pd.DataFrame,
                    model_version: str) -> int:
    """Persist one row per served prediction. Best-effort: logging must never
    break scoring, so callers wrap this and swallow failures."""
    rows = []
    for src, (_, s) in zip(records, scored.iterrows()):
        delay = s.get("expected_delay_days")
        rows.append(PredictionLog(
            model_version=model_version,
            delivery_ref=str(src.get("delivery_id") or src.get("delivery_ref") or "") or None,
            supplier_id=src.get("supplier_id"),
            material_type=src.get("material_type"),
            route_type=src.get("route_type"),
            quantity=int(src["quantity"]) if src.get("quantity") is not None else None,
            order_date=pd.to_datetime(src.get("order_date")).date() if src.get("order_date") else None,
            promised_date=pd.to_datetime(src.get("promised_date")).date() if src.get("promised_date") else None,
            predicted_risk=float(s["risk"]),
            predicted_band=str(s["risk_band"]),
            predicted_late=int(float(s["risk"]) >= LATE_DECISION_THRESHOLD),
            expected_delay_days=(None if delay is None or pd.isna(delay) else float(delay)),
        ))
    db.add_all(rows)
    db.commit()
    return len(rows)


class OutcomeIn(BaseModel):
    """Report what actually happened for a previously predicted delivery."""

    prediction_id: int | None = None      # exact row, when the caller kept the id
    delivery_ref: str | None = None       # or match on the caller's own id
    actual_date: date
    grace_days: int = 1                   # per-material tolerance; see ml/labeling


@router.post("/outcomes")
def record_outcomes(outcomes: list[OutcomeIn],
                    db: Session = Depends(get_session)) -> dict:
    """Attach real outcomes to logged predictions."""
    if not outcomes:
        raise HTTPException(status_code=400, detail="No outcomes supplied.")

    updated, missed = 0, []
    for o in outcomes:
        q = db.query(PredictionLog)
        if o.prediction_id is not None:
            q = q.filter(PredictionLog.id == o.prediction_id)
        elif o.delivery_ref:
            q = q.filter(PredictionLog.delivery_ref == o.delivery_ref)
        else:
            missed.append("outcome needs prediction_id or delivery_ref")
            continue

        row = q.order_by(PredictionLog.predicted_at.desc()).first()
        if row is None:
            missed.append(o.delivery_ref or str(o.prediction_id))
            continue

        row.actual_date = o.actual_date
        if row.promised_date:
            delay = (o.actual_date - row.promised_date).days
            row.actual_delay_days = float(delay)
            row.actual_late = int(delay > o.grace_days)
        row.outcome_recorded_at = datetime.now(timezone.utc)
        updated += 1

    db.commit()
    return {"updated": updated, "unmatched": missed}


@router.get("/accuracy")
def realized_accuracy(model_version: str | None = None,
                      db: Session = Depends(get_session)) -> dict:
    """Realized accuracy of served predictions that have known outcomes."""
    q = db.query(PredictionLog).filter(PredictionLog.actual_late.isnot(None))
    if model_version:
        q = q.filter(PredictionLog.model_version == model_version)
    rows = q.all()

    total_logged = db.query(func.count(PredictionLog.id)).scalar() or 0
    if not rows:
        return {"predictions_logged": total_logged, "with_known_outcome": 0,
                "note": "No outcomes recorded yet — POST /outcomes to close the loop."}

    tp = sum(r.predicted_late == 1 and r.actual_late == 1 for r in rows)
    fp = sum(r.predicted_late == 1 and r.actual_late == 0 for r in rows)
    fn = sum(r.predicted_late == 0 and r.actual_late == 1 for r in rows)
    tn = sum(r.predicted_late == 0 and r.actual_late == 0 for r in rows)
    n = len(rows)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None

    # Calibration: within each risk band, what fraction actually ran late?
    calibration = {}
    for band in ("green", "yellow", "red"):
        sel = [r for r in rows if r.predicted_band == band]
        if sel:
            calibration[band] = {
                "n": len(sel),
                "actual_late_rate": round(sum(r.actual_late for r in sel) / len(sel), 3),
            }

    delay_rows = [r for r in rows
                  if r.expected_delay_days is not None and r.actual_delay_days is not None
                  and r.actual_late == 1]
    mae = (round(sum(abs(r.expected_delay_days - r.actual_delay_days)
                     for r in delay_rows) / len(delay_rows), 2)
           if delay_rows else None)

    return {
        "predictions_logged": total_logged,
        "with_known_outcome": n,
        "accuracy": round((tp + tn) / n, 3),
        "precision_late": round(precision, 3) if precision is not None else None,
        "recall_late": round(recall, 3) if recall is not None else None,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        # The money shot: red should run late far more often than green.
        "calibration_by_band": calibration,
        "expected_delay_mae_days": mae,
    }


@router.get("/predictions")
def recent_predictions(limit: int = 50, only_open: bool = False,
                       db: Session = Depends(get_session)) -> dict:
    """Recent log rows — the audit trail behind the accuracy numbers."""
    q = db.query(PredictionLog)
    if only_open:
        q = q.filter(PredictionLog.actual_late.is_(None))
    rows = q.order_by(PredictionLog.predicted_at.desc()).limit(limit).all()
    return {"count": len(rows), "predictions": [
        {"id": r.id, "predicted_at": r.predicted_at, "model_version": r.model_version,
         "delivery_ref": r.delivery_ref, "supplier_id": r.supplier_id,
         "material_type": r.material_type, "promised_date": r.promised_date,
         "predicted_risk": r.predicted_risk, "predicted_band": r.predicted_band,
         "expected_delay_days": r.expected_delay_days,
         "actual_date": r.actual_date, "actual_late": r.actual_late}
        for r in rows]}
