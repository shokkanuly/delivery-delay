"""Audit router (Stage 3, docs/plans/mvp-reshape.md D4): upload a real 1C/Excel
delivery export, get back whether this is worth pursuing as a pilot.

  POST /audit/history  multipart file -> {quality, scorecard, backtest}

Admin-key protected today (api.security.require_admin); Stage 6 adds an
approver role and this gets `require_role("admin", "approver")` instead --
same X-API-Key header, a wider set of accepted keys.

Nothing uploaded is written to disk unless `?save=true` (pilot mode), and
even then it goes to data/customer_uploads/ (gitignored), never the
`deliveries` table -- that table's schema is shared with the synthetic demo
data and isn't customer-upload-shaped yet (a real intake pipeline is outside
Stage 3's scope).
"""
from __future__ import annotations

import pathlib
import time

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from api.security import require_admin
from ml.ingest import DeliveryCSVError, load_export
from ml.scorecard import material_breakdown, supplier_scorecard
from ml.train import time_split_backtest

router = APIRouter(prefix="/audit", tags=["audit"])

# A year of one site's deliveries is a few thousand rows; 10 MB is generous
# headroom for a CSV/Excel-as-CSV export while still bounding memory/CPU on
# an unauthenticated-by-content upload.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
UPLOAD_DIR = pathlib.Path("data/customer_uploads")


def _save_upload(filename: str | None, raw: bytes) -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = (filename or "upload.csv").replace("/", "_").replace("\\", "_")
    path = UPLOAD_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}-{safe_name}"
    path.write_bytes(raw)
    return str(path)


@router.post("/history", dependencies=[Depends(require_admin)])
async def audit_history(file: UploadFile = File(...), save: bool = False) -> dict:
    """Quality report + supplier scorecard + time-split backtest, computed
    fresh on the uploaded data with a throwaway temp artifact -- never
    ml.train.ARTIFACT_PATH, the one /predict serves."""
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File too large (> {MAX_UPLOAD_BYTES // (1024 * 1024)} MB).")

    try:
        df, report = load_export(raw)
    except DeliveryCSVError as exc:
        raise HTTPException(400, str(exc))

    saved_to = _save_upload(file.filename, raw) if save else None

    scorecard = supplier_scorecard(df)
    materials = material_breakdown(df)
    backtest = time_split_backtest(df)

    return {
        "filename": file.filename,
        "saved_to": saved_to,
        "quality": {
            "rows_total": report.rows_total,
            "rows_kept": report.rows_kept,
            "rows_dropped": report.rows_dropped,
            "bad_dates": report.bad_dates,
            "bad_quantity": report.bad_quantity,
            "duplicates": report.duplicates,
            "promised_before_order": report.promised_before_order,
            "route_type_defaulted": report.route_type_defaulted,
            "unmapped_columns": report.unmapped_columns,
            "summary": report.summary(),
        },
        "scorecard": {
            "suppliers": scorecard.to_dict("records"),
            "by_material": materials.to_dict("records"),
        },
        "backtest": backtest,
        "model_beats_baseline": backtest.get("beats_baseline"),
    }
