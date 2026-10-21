"""History audit, isolated from the serving model and database."""
from __future__ import annotations

import os
from pathlib import Path
import threading
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from api.schemas import HistoryAuditOut
from api.security import require_admin
from ml.audit import build_audit_report
from ml.ingest import load_export

router = APIRouter(tags=["audit"])
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_AUDIT_ROWS = 10_000
_audit_lock = threading.Lock()


@router.post("/audit/history", response_model=HistoryAuditOut,
             dependencies=[Depends(require_admin)])
def audit_history(file: UploadFile = File(...), synthetic: bool = Form(False),
                  save: bool = False) -> HistoryAuditOut:
    """CSV → quality, descriptive scorecard and a 70/30 time-split backtest.

    No serving artifact/cache or business tables are touched. Persistence is
    opt-in and requires SITEPULSE_AUDIT_DIR on a persistent customer volume.
    Approver role keys will be introduced alongside the booking roles in Stage 6.
    """
    storage = os.getenv("SITEPULSE_AUDIT_DIR")
    if save and not storage:
        raise HTTPException(409, "Сохранение отключено: настройте SITEPULSE_AUDIT_DIR на постоянном диске клиента.")
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(422, "Сохраните выгрузку как CSV. XLSX пока не поддерживается.")
    raw = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Файл превышает лимит 5 МБ.")
    if not raw.strip():
        raise HTTPException(422, "CSV-файл пуст.")
    if not _audit_lock.acquire(blocking=False):
        raise HTTPException(429, "Другой аудит ещё выполняется. Повторите запрос позже.")
    try:
        try:
            frame, quality = load_export(raw)
            if quality.rows_total > MAX_AUDIT_ROWS:
                raise HTTPException(413, "В выгрузке больше 10 000 строк. Разделите файл по периоду.")
            report = HistoryAuditOut(**build_audit_report(frame, quality, synthetic))
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, f"Не удалось обработать CSV: {exc}") from exc

        if save:
            audit_id = uuid4().hex
            folder = Path(storage) / audit_id
            created = False
            try:
                folder.mkdir(parents=True, mode=0o700)
                created = True
                frame.to_csv(folder / "deliveries.csv", index=False)
                report.saved = True
                report.audit_id = audit_id
                (folder / "report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
            except OSError as exc:
                # Remove only files from this request's newly created directory.
                if created:
                    try:
                        for name in ("deliveries.csv", "report.json"):
                            (folder / name).unlink(missing_ok=True)
                        folder.rmdir()
                    except OSError:
                        pass
                raise HTTPException(503, "Не удалось сохранить аудит на постоянный диск.") from exc
        return report
    finally:
        _audit_lock.release()
