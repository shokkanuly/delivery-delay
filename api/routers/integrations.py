"""Signed ingest from gate scanners and 1C receipt exports, with a review queue and an audit log.

Patterns ported from JanaМен (shokkanuly/posttech):
- HMAC-SHA256 signatures with timestamp + one-time nonce (api/signing.py); replayed nonces are refused;
- the sender's event_id makes every push idempotent, so a retry never applies an arrival twice;
- events are matched by the business key (delivery_ref) only; anything unmatched waits in a review queue;
- every applied batch is written to an append-only audit log.

Each "arrived" event closes the loop on a served prediction (same logic as POST /outcomes),
so realized accuracy (/accuracy) fills in from the site's own gate data instead of manual entry.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api import signing
from api.routers.monitoring import apply_outcome, log_audit
from api.security import require_admin
from db.database import get_session
from db.models import AuditEvent, IngestNonce, IntegrationEvent

router = APIRouter(prefix="/integrations", tags=["integrations"])

INGEST_KEYS_ENV = "SITEPULSE_INGEST_KEYS"
MAX_BODY = 512 * 1024
GATE_EVENTS_PATH = "/integrations/gate-events"


class GateEvent(BaseModel):
    event_id: str = Field(..., min_length=1, max_length=64)
    kind: Literal["arrived"] = "arrived"
    delivery_ref: str = Field(..., min_length=1, max_length=64)
    occurred_on: date
    gate: str | None = Field(None, max_length=32)
    grace_days: int = Field(1, ge=0, le=14)


class GateBatch(BaseModel):
    events: list[GateEvent] = Field(..., min_length=1, max_length=500)


async def verified_sender(request: Request, db: Session = Depends(get_session)) -> tuple[str, bytes]:
    """Return (key_id, raw body) of a correctly signed, never-seen request."""
    keys = signing.keys_from_env(os.getenv(INGEST_KEYS_ENV))
    if not keys:
        raise HTTPException(503, f"Signed ingest is disabled: set {INGEST_KEYS_ENV}.")
    body = await request.body()
    if len(body) > MAX_BODY:
        raise HTTPException(413, "Batch too large.")
    try:
        nonce = signing.verify(request.headers, keys, request.method, request.url.path, body)
    except signing.SignatureError:
        raise HTTPException(401, "Invalid or expired signature.")
    key_id = request.headers["x-key-id"]
    db.add(IngestNonce(nonce=nonce, key_id=key_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Replayed request (nonce already used).")
    return key_id, body


@router.post("/gate-events")
def gate_events(sender: tuple[str, bytes] = Depends(verified_sender),
                db: Session = Depends(get_session)) -> dict:
    """Arrivals from a gate scanner or 1C receipts. Signed; idempotent per (sender, event_id)."""
    key_id, body = sender
    try:
        batch = GateBatch.model_validate_json(body)
    except ValidationError as e:
        raise HTTPException(422, e.errors(include_url=False, include_context=False))

    counts = {"applied": 0, "unmatched": 0, "duplicate": 0}
    for ev in batch.events:
        exists = db.query(IntegrationEvent.id).filter_by(source=key_id, event_id=ev.event_id).first()
        if exists:
            counts["duplicate"] += 1
            continue
        matched = apply_outcome(db, ev.occurred_on, ev.grace_days, delivery_ref=ev.delivery_ref)
        status = "applied" if matched else "unmatched"
        db.add(IntegrationEvent(source=key_id, event_id=ev.event_id, kind=ev.kind,
                                delivery_ref=ev.delivery_ref, occurred_on=ev.occurred_on,
                                gate=ev.gate, status=status))
        db.flush()  # a duplicate event_id inside the same batch hits the unique constraint here
        counts[status] += 1
    log_audit(db, f"ingest:{key_id}", "gate_events.received", None, counts)
    db.commit()
    return counts


@router.get("/review", dependencies=[Depends(require_admin)])
def review_queue(limit: int = 100, db: Session = Depends(get_session)) -> dict:
    """Events that matched no served prediction: fix the delivery_ref mapping, never guess."""
    rows = (db.query(IntegrationEvent).filter_by(status="unmatched")
            .order_by(IntegrationEvent.received_at.desc()).limit(min(limit, 500)).all())
    return {"count": len(rows), "events": [
        {"source": r.source, "event_id": r.event_id, "delivery_ref": r.delivery_ref,
         "occurred_on": r.occurred_on, "gate": r.gate, "received_at": r.received_at} for r in rows]}


@router.get("/status", dependencies=[Depends(require_admin)])
def status(db: Session = Depends(get_session)) -> dict:
    """Integration telemetry for the console (JanaМен's adapter card)."""
    by_status = dict(db.query(IntegrationEvent.status, func.count(IntegrationEvent.id))
                     .group_by(IntegrationEvent.status).all())
    last = db.query(func.max(IntegrationEvent.received_at)).scalar()
    return {"configured_senders": len(signing.keys_from_env(os.getenv(INGEST_KEYS_ENV))),
            "events": {"applied": by_status.get("applied", 0), "unmatched": by_status.get("unmatched", 0)},
            "last_event_at": last, "checked_at": datetime.now(timezone.utc)}


@router.get("/audit", dependencies=[Depends(require_admin)])
def audit(limit: int = 100, db: Session = Depends(get_session)) -> dict:
    rows = db.query(AuditEvent).order_by(AuditEvent.id.desc()).limit(min(limit, 500)).all()
    return {"count": len(rows), "events": [
        {"at": r.at, "actor": r.actor, "action": r.action, "target": r.target, "details": r.details}
        for r in rows]}
