"""Served-model state shared by the routers: the cached artifact and the
helpers that turn a scored row into an API response."""
from __future__ import annotations

from functools import lru_cache

import pandas as pd
from sqlalchemy.orm import Session

from api.routers.monitoring import log_predictions
from ml.predict import load_artifact
from ml.train import ARTIFACT_PATH, fit_and_save


@lru_cache
def get_artifact() -> dict:
    """Load the model artifact once; train one on first use if none exists."""
    if not ARTIFACT_PATH.exists():
        fit_and_save()
    return load_artifact()


def prediction_fields(row: pd.Series) -> dict:
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


def supplier_coverage(art: dict) -> float | None:
    """Share of suppliers in the scored reference data that the served model
    has history for. Below 1.0 means scores silently fall back to cold-start."""
    from api.data_sources import read_reference
    try:
        scored = set(read_reference("delay_prediction.csv")["supplier_id"])
    except Exception:
        return None
    known = set(art["snapshot"]["supplier"].index) if hasattr(art["snapshot"]["supplier"], "index") \
        else set(art["snapshot"]["supplier"])
    return round(len(scored & known) / len(scored), 3) if scored else None


def log_safely(db: Session, records: list[dict], scored: pd.DataFrame) -> None:
    """Record served predictions for later scoring against reality.

    Best-effort by design: an audit-log failure must never take down scoring.
    """
    try:
        log_predictions(db, records, scored, get_artifact().get("model_version", "unknown"))
    except Exception:  # noqa: BLE001
        db.rollback()
