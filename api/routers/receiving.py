"""Site-scoped receiving. No dependency on a model, public project, or ERP connection."""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Response, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.receiving_service import (audit, check_payload, current_revision, decision_for, iso, notify_coordinators,
                                   lock_receipt, make_revision, now, receipt_packet, scoped, validate_acceptance)
from api.schemas import (EvidenceGrantIn, PlanStatusIn, ReceiptCorrectionIn, ReceiptDecisionIn,
                         ReceiptIn, ReceivingActorIn, ReceivingDocumentIn, ReceivingPlanIn, ReceivingSiteIn)
from api.security import (credential_hash, receiving_actor, receiving_coordinator, receiving_writer,
                          require_admin)
from db.database import get_session
from db.models import (EvidenceGrant, Receipt, ReceiptAttachment, ReceiptAttestation, ReceiptRevision,
                       ReceivingActor, ReceivingAudit, ReceivingDocument, ReceivingPlan, ReceivingSite)
from engines.receiving import digest, reconciliation, plan_progress

router = APIRouter(prefix="/receiving", tags=["receiving"])
MAX_MEDIA = 5 * 1024 * 1024
MAX_ATTACHMENTS = 6


def feature(name):
    if os.getenv(name, "0") != "1":
        raise HTTPException(403, "Extension disabled until its pilot/design-partner gate is agreed")


@router.post("/sites", dependencies=[Depends(require_admin)], status_code=201)
def create_site(body: ReceivingSiteIn, db: Session = Depends(get_session)):
    site = ReceivingSite(id=str(uuid4()), **body.model_dump(), created_at=now())
    db.add(site)
    db.commit()
    return {"id": site.id, "name": site.name, "timezone": site.timezone}


@router.post("/sites/{site_id}/actors", dependencies=[Depends(require_admin)], status_code=201)
def create_actor(site_id: UUID, body: ReceivingActorIn, db: Session = Depends(get_session)):
    if db.get(ReceivingSite, str(site_id)) is None:
        raise HTTPException(404, "Site not found")
    key = "SP-" + secrets.token_urlsafe(32)
    actor = ReceivingActor(id=str(uuid4()), site_id=str(site_id), **body.model_dump(),
                           key_hash=credential_hash(key), active=True, created_at=now())
    db.add(actor)
    audit(db, actor, "actor.provisioned", actor.id, {"operator": "admin", "role": actor.role})
    db.commit()
    return {"id": actor.id, "name": actor.name, "role": actor.role, "site_id": actor.site_id,
            "credential": key, "notice": "Shown once. Give only to this named person."}


@router.post("/actors/{actor_id}/revoke", dependencies=[Depends(require_admin)])
def revoke_actor(actor_id: UUID, db: Session = Depends(get_session)):
    actor = db.get(ReceivingActor, str(actor_id))
    if actor is None:
        raise HTTPException(404, "Actor not found")
    actor.active = False
    audit(db, actor, "actor.revoked", actor.id, {"operator": "admin"})
    db.commit()
    return {"revoked": True}


@router.get("/me")
def me(actor=Depends(receiving_actor), db: Session = Depends(get_session)):
    site = db.get(ReceivingSite, actor.site_id)
    return {"id": actor.id, "name": actor.name, "role": actor.role,
            "site": {"id": site.id, "name": site.name, "timezone": site.timezone},
            "features": {"reconciliation": os.getenv("SITEPULSE_ENABLE_RECONCILIATION") == "1",
                         "partner_sharing": os.getenv("SITEPULSE_ENABLE_PARTNER_SHARING") == "1",
                         "operations": os.getenv("SITEPULSE_ENABLE_OPERATIONS") == "1"}}


@router.post("/plans", status_code=201)
def create_plan(body: ReceivingPlanIn, actor=Depends(receiving_coordinator), db: Session = Depends(get_session)):
    payload = body.model_dump(mode="json")
    row = ReceivingPlan(id=str(uuid4()), site_id=actor.site_id, reference=body.reference,
                        payload=payload, status="expected", created_by=actor.id, created_at=now())
    db.add(row)
    audit(db, actor, "plan.created", row.id, {"reference": body.reference})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        old = db.query(ReceivingPlan).filter_by(site_id=actor.site_id, reference=body.reference).first()
        if old and old.payload == payload:
            return {"id": old.id, "status": old.status, **old.payload}
        raise HTTPException(409, "Reference already belongs to a different plan")
    return {"id": row.id, "status": row.status, **payload}


@router.get("/plans")
def plans(limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0),
          actor=Depends(receiving_actor), db: Session = Depends(get_session)):
    query = db.query(ReceivingPlan).filter_by(site_id=actor.site_id)
    return {"total": query.count(), "plans": [{"id": r.id, "status": r.status, **r.payload}
            for r in query.order_by(ReceivingPlan.created_at.desc(), ReceivingPlan.id).offset(offset).limit(limit).all()]}


@router.post("/plans/{plan_id}/status")
def plan_status(plan_id: UUID, body: PlanStatusIn, actor=Depends(receiving_coordinator), db: Session = Depends(get_session)):
    row = scoped(db, ReceivingPlan, plan_id, actor)
    row.status = body.status
    audit(db, actor, "plan." + body.status, row.id, {"reason": body.reason})
    db.commit()
    return {"id": row.id, "status": row.status}


@router.get("/plans/{plan_id}")
def plan_detail(plan_id: UUID, actor=Depends(receiving_actor), db: Session = Depends(get_session)):
    plan = scoped(db, ReceivingPlan, plan_id, actor)
    revisions = (db.query(ReceiptRevision).join(Receipt, Receipt.id == ReceiptRevision.receipt_id)
                 .filter(Receipt.site_id == actor.site_id, ReceiptRevision.number == Receipt.revision,
                         ReceiptRevision.payload["plan_id"].as_string() == plan.id)
                 .order_by(ReceiptRevision.received_at, ReceiptRevision.id).all())
    records = []
    links = []
    for revision in revisions:
        decision = decision_for(db, revision)
        records.append({"payload": revision.payload, "decision": decision.payload if decision else None})
        links.append({"receipt_id": revision.receipt_id, "revision": revision.number,
                      "observed_at": revision.payload["observed_at"],
                      "evidence_status": decision.payload["decision"] if decision else "recorded"})
    return {"plan": {"id": plan.id, "status": plan.status, **plan.payload},
            "progress": plan_progress(plan.payload["lines"], records), "receipts": links}


def retry_revision(db, actor, operation_id, request_digest):
    old = db.query(ReceiptRevision).filter_by(site_id=actor.site_id, operation_id=str(operation_id)).first()
    if old is not None:
        if old.actor_id != actor.id or old.request_digest != request_digest:
            raise HTTPException(409, "Operation ID reused with different content or actor")
        receipt = scoped(db, Receipt, old.receipt_id, actor)
        return {"duplicate": True, "applied_revision": old.number, "receipt": receipt_packet(db, receipt)}
    return None


@router.post("/receipts", status_code=201)
def create_receipt(body: ReceiptIn, actor=Depends(receiving_writer), db: Session = Depends(get_session)):
    request_digest = digest(body.model_dump(mode="json"))
    old = retry_revision(db, actor, body.operation_id, request_digest)
    if old:
        return old
    payload = body.payload.model_dump(mode="json")
    check_payload(db, payload, actor)
    receipt = Receipt(id=str(body.receipt_id), site_id=actor.site_id, revision=1,
                      created_by=actor.id, created_at=now(), mutation=0)
    db.add(receipt)
    try:
        db.flush()
        make_revision(db, actor, receipt, body.operation_id, payload, request_digest)
        db.commit()
    except IntegrityError:
        db.rollback()
        old = retry_revision(db, actor, body.operation_id, request_digest)
        if old:
            return old
        raise HTTPException(409, "Receipt ID already exists; use a new ID or a correction")
    return {"duplicate": False, "applied_revision": 1, "receipt": receipt_packet(db, receipt)}


@router.get("/receipts")
def receipts(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
             actor=Depends(receiving_actor), db: Session = Depends(get_session)):
    query = db.query(Receipt).filter_by(site_id=actor.site_id)
    return {"total": query.count(), "receipts": [receipt_packet(db, r, history=False)
            for r in query.order_by(Receipt.created_at.desc(), Receipt.id).offset(offset).limit(limit).all()]}


@router.get("/receipts/{receipt_id}")
def get_receipt(receipt_id: UUID, actor=Depends(receiving_actor), db: Session = Depends(get_session)):
    return receipt_packet(db, scoped(db, Receipt, receipt_id, actor))


@router.post("/receipts/{receipt_id}/corrections")
def correct_receipt(receipt_id: UUID, body: ReceiptCorrectionIn, actor=Depends(receiving_writer),
                    db: Session = Depends(get_session)):
    request_digest = digest({"receipt_id": str(receipt_id), **body.model_dump(mode="json")})
    old = retry_revision(db, actor, body.operation_id, request_digest)
    if old:
        return old
    receipt = lock_receipt(db, receipt_id, actor)
    # Another retry can have committed while this request waited for the lock.
    old = retry_revision(db, actor, body.operation_id, request_digest)
    if old:
        db.rollback()
        return old
    if actor.role != "coordinator" and receipt.created_by != actor.id:
        raise HTTPException(403, "Only the recorder or coordinator can correct this receipt")
    if receipt.revision != body.expected_revision:
        raise HTTPException(409, "Receipt changed; review the latest revision")
    payload = body.payload.model_dump(mode="json")
    if payload["provenance"] != current_revision(db, receipt).payload["provenance"]:
        raise HTTPException(422, "Provenance cannot be promoted by correction")
    check_payload(db, payload, actor)
    receipt.revision += 1
    make_revision(db, actor, receipt, body.operation_id, payload, request_digest, body.reason)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        old = retry_revision(db, actor, body.operation_id, request_digest)
        if old:
            return old
        raise HTTPException(409, "Concurrent correction; reload receipt")
    return {"duplicate": False, "applied_revision": receipt.revision, "receipt": receipt_packet(db, receipt)}


@router.post("/receipts/{receipt_id}/revisions/{number}/attachments", status_code=201)
def upload_attachment(receipt_id: UUID, number: int, file: UploadFile = File(...),
                      actor=Depends(receiving_writer), db: Session = Depends(get_session)):
    content = file.file.read(MAX_MEDIA + 1)
    if not content or len(content) > MAX_MEDIA:
        raise HTTPException(413, "Evidence must be 1 byte to 5 MB")
    content_type = ("image/jpeg" if content.startswith(b"\xff\xd8\xff") else
                    "image/png" if content.startswith(b"\x89PNG\r\n\x1a\n") else
                    "application/pdf" if content.startswith(b"%PDF-") else None)
    if content_type is None:
        raise HTTPException(415, "Use a JPEG, PNG or PDF evidence file")
    receipt = lock_receipt(db, receipt_id, actor)
    rev = db.query(ReceiptRevision).filter_by(receipt_id=receipt.id, number=number).first()
    if rev is None:
        raise HTTPException(404, "Receipt revision not found")
    sha = hashlib.sha256(content).hexdigest()
    old = db.query(ReceiptAttachment).filter_by(revision_id=rev.id, digest=sha).first()
    if old:
        db.rollback()
        return {"id": old.id, "sha256": sha, "duplicate": True}
    if receipt.revision != number:
        raise HTTPException(409, "Attachment targets a superseded revision")
    if decision_for(db, rev):
        raise HTTPException(409, "Evidence is attested; create a correction before adding files")
    if db.query(ReceiptAttachment).filter_by(revision_id=rev.id).count() >= MAX_ATTACHMENTS:
        raise HTTPException(422, "At most six attachments per revision")
    item = ReceiptAttachment(id=str(uuid4()), revision_id=rev.id, site_id=actor.site_id,
                             actor_id=actor.id, digest=sha, content_type=content_type,
                             size=len(content), content=content, created_at=now())
    db.add(item)
    audit(db, actor, "receipt.attachment_added", receipt.id, {"revision": number, "sha256": sha})
    db.commit()
    return {"id": item.id, "sha256": sha, "duplicate": False}


@router.get("/attachments/{attachment_id}")
def download_attachment(attachment_id: UUID, actor=Depends(receiving_actor), db: Session = Depends(get_session)):
    item = scoped(db, ReceiptAttachment, attachment_id, actor)
    audit(db, actor, "attachment.downloaded", item.id)
    db.commit()
    extension = {"image/jpeg": "jpg", "image/png": "png", "application/pdf": "pdf"}[item.content_type]
    return Response(item.content, media_type=item.content_type,
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                             "Content-Security-Policy": "sandbox; default-src 'none'",
                             "Content-Disposition": f'attachment; filename="evidence-{item.id}.{extension}"'})


@router.post("/receipts/{receipt_id}/decisions")
def attest(receipt_id: UUID, body: ReceiptDecisionIn, actor=Depends(receiving_writer), db: Session = Depends(get_session)):
    receipt = lock_receipt(db, receipt_id, actor)
    payload = body.model_dump(mode="json")
    fingerprint = digest({"receipt_id": str(receipt_id), **payload})
    existing = db.get(ReceiptAttestation, str(body.decision_id))
    if existing:
        if existing.site_id != actor.site_id or existing.actor_id != actor.id or existing.digest != fingerprint:
            raise HTTPException(409, "Decision ID reused with different content or actor")
        db.rollback()
        return receipt_packet(db, receipt)
    if receipt.revision != body.expected_revision:
        raise HTTPException(409, "Receipt changed; confirm the latest revision")
    rev = current_revision(db, receipt)
    previous = decision_for(db, rev)
    if previous and (actor.role != "coordinator" or len(body.reason) < 3):
        raise HTTPException(409, "Changing a decision needs coordinator review and a reason")
    validate_acceptance(rev.payload, payload)
    db.add(ReceiptAttestation(id=str(body.decision_id), revision_id=rev.id, site_id=actor.site_id,
                             actor_id=actor.id, payload=payload, digest=fingerprint, created_at=now()))
    audit(db, actor, "receipt." + body.decision, receipt.id, {"revision": receipt.revision, "decision_id": str(body.decision_id)})
    notify_coordinators(db, actor, "decision:" + str(body.decision_id),
                        {"kind": body.decision, "receipt_id": receipt.id, "reference": rev.payload["reference"]})
    db.commit()
    return receipt_packet(db, receipt)


@router.get("/receipts/{receipt_id}/export")
def export_receipt(receipt_id: UUID, actor=Depends(receiving_actor), db: Session = Depends(get_session)):
    packet = receipt_packet(db, scoped(db, Receipt, receipt_id, actor))
    audit(db, actor, "receipt.exported", receipt_id, {"revision": packet["current_revision"]})
    db.commit()
    return packet


@router.get("/audit")
def audit_log(limit: int = Query(100, ge=1, le=500), actor=Depends(receiving_coordinator), db: Session = Depends(get_session)):
    rows = (db.query(ReceivingAudit).filter_by(site_id=actor.site_id)
            .order_by(ReceivingAudit.id.desc()).limit(limit).all())
    return {"events": [{"id": r.id, "actor_id": r.actor_id, "action": r.action,
                        "target": r.target, "details": r.details, "at": iso(r.at)} for r in rows]}


@router.post("/documents", status_code=201)
def add_document(body: ReceivingDocumentIn, actor=Depends(receiving_coordinator), db: Session = Depends(get_session)):
    feature("SITEPULSE_ENABLE_RECONCILIATION")
    scoped(db, ReceivingPlan, body.plan_id, actor)
    payload = body.model_dump(mode="json")
    old = db.get(ReceivingDocument, str(body.document_id))
    if old:
        if old.site_id != actor.site_id or old.payload != payload:
            raise HTTPException(409, "Document ID conflict")
        return {"id": old.id, **old.payload}
    row = ReceivingDocument(id=str(body.document_id), site_id=actor.site_id, plan_id=str(body.plan_id),
                            payload=payload, actor_id=actor.id, created_at=now())
    db.add(row)
    audit(db, actor, "document.recorded", row.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        old = db.get(ReceivingDocument, str(body.document_id))
        if old and old.site_id == actor.site_id and old.payload == payload:
            return {"id": old.id, **old.payload}
        raise HTTPException(409, "Document ID conflict")
    return {"id": row.id, **payload}


@router.get("/documents")
def documents(limit: int = Query(100, ge=1, le=200), actor=Depends(receiving_actor), db: Session = Depends(get_session)):
    feature("SITEPULSE_ENABLE_RECONCILIATION")
    rows = (db.query(ReceivingDocument).filter_by(site_id=actor.site_id)
            .order_by(ReceivingDocument.created_at.desc()).limit(limit).all())
    return {"documents": [{"id": r.id, **r.payload} for r in rows]}


@router.get("/documents/{document_id}/reconciliation")
def reconcile_document(document_id: UUID, actor=Depends(receiving_actor), db: Session = Depends(get_session)):
    feature("SITEPULSE_ENABLE_RECONCILIATION")
    doc = scoped(db, ReceivingDocument, document_id, actor)
    totals = {}
    receipt_ids = []
    # Join to the current revision only. Confirmations on superseded revisions never count.
    revisions = (db.query(ReceiptRevision).join(Receipt, Receipt.id == ReceiptRevision.receipt_id)
                 .filter(Receipt.site_id == actor.site_id, ReceiptRevision.number == Receipt.revision).all())
    plan = scoped(db, ReceivingPlan, doc.plan_id, actor)
    for rev in revisions:
        if rev.payload["plan_id"] != doc.plan_id:
            continue
        decision = decision_for(db, rev)
        if decision is None or decision.payload["decision"] != "confirmed":
            continue
        accepted = {x["line_id"]: Decimal(x["quantity"]) for x in decision.payload["accepted"]}
        receipt_ids.append(rev.receipt_id)
        for line in rev.payload["lines"]:
            key = (line["line_id"], line["material"], line["unit"])
            totals[key] = totals.get(key, Decimal(0)) + accepted.get(line["line_id"], Decimal(0))
    actual = [{"line_id": key[0], "material": key[1], "unit": key[2], "quantity": str(qty)}
              for key, qty in totals.items()]
    result = reconciliation(doc.payload["lines"], actual)
    related = db.query(ReceivingDocument).filter_by(site_id=actor.site_id, plan_id=doc.plan_id).count()
    return {"document_id": doc.id, "provenance": plan.payload["provenance"], "lines": result,
            "receipt_ids": receipt_ids, "requires_review": related > 1 or any(x["status"] != "matched" for x in result),
            "related_document_count": related,
            "notice": "Compares this document to accepted receipts for the plan. Multiple documents require allocation review; no automatic accounting acceptance."}


@router.post("/grants", status_code=201)
def create_grant(body: EvidenceGrantIn, actor=Depends(receiving_coordinator), db: Session = Depends(get_session)):
    feature("SITEPULSE_ENABLE_PARTNER_SHARING")
    receipt = lock_receipt(db, body.receipt_id, actor)
    packet = receipt_packet(db, receipt)
    if receipt.revision != body.expected_revision or not packet["current"]["complete_confirmed"]:
        raise HTTPException(409, "Only a current, complete, confirmed REAL receipt can be shared")
    if not now() < body.expires_at <= now() + timedelta(days=30):
        raise HTTPException(422, "Grant expiry must be in the next 30 days")
    key = "EVID-" + secrets.token_urlsafe(32)
    row = EvidenceGrant(id=str(uuid4()), site_id=actor.site_id, receipt_id=receipt.id,
                        revision=receipt.revision, key_hash=credential_hash(key), recipient=body.recipient,
                        purpose=body.purpose, consent_reference=body.consent_reference,
                        expires_at=body.expires_at, revoked=False, actor_id=actor.id, created_at=now())
    db.add(row)
    audit(db, actor, "grant.created", row.id, {"receipt_id": receipt.id, "revision": receipt.revision,
                                              "recipient": body.recipient, "purpose": body.purpose})
    db.commit()
    return {"id": row.id, "credential": key, "expires_at": iso(row.expires_at),
            "scope": "One revision; redacted quantities/timing/confirmation metadata only. No photos, GPS or actor names."}


@router.get("/grants")
def grants(actor=Depends(receiving_coordinator), db: Session = Depends(get_session)):
    rows = db.query(EvidenceGrant).filter_by(site_id=actor.site_id).order_by(EvidenceGrant.created_at.desc()).limit(200).all()
    return {"grants": [{"id": r.id, "receipt_id": r.receipt_id, "revision": r.revision,
                       "recipient": r.recipient, "purpose": r.purpose, "expires_at": iso(r.expires_at),
                       "revoked": r.revoked} for r in rows]}


@router.post("/grants/{grant_id}/revoke")
def revoke_grant(grant_id: UUID, actor=Depends(receiving_coordinator), db: Session = Depends(get_session)):
    row = scoped(db, EvidenceGrant, grant_id, actor)
    row.revoked = True
    audit(db, actor, "grant.revoked", row.id)
    db.commit()
    return {"revoked": True}


@router.get("/shared-evidence")
def shared_evidence(x_evidence_key: str | None = Header(None), db: Session = Depends(get_session)):
    feature("SITEPULSE_ENABLE_PARTNER_SHARING")
    grant = db.query(EvidenceGrant).filter_by(key_hash=credential_hash(x_evidence_key or ""), revoked=False).first()
    if grant is None or datetime.fromisoformat(iso(grant.expires_at)) <= now():
        raise HTTPException(401, "Evidence access invalid, expired or revoked")
    owner = db.get(ReceivingActor, grant.actor_id)
    if owner is None or not owner.active:
        raise HTTPException(401, "Issuing actor revoked")
    receipt = scoped(db, Receipt, grant.receipt_id, owner)
    packet = receipt_packet(db, receipt)
    if receipt.revision != grant.revision or not packet["current"]["complete_confirmed"]:
        raise HTTPException(409, "Evidence changed or is disputed; request a new authorised grant")
    current = packet["current"]
    payload = current["payload"]
    result = {"schema_version": 1, "receipt_id": receipt.id, "revision": grant.revision,
              "observed_at": payload["observed_at"], "time_source": payload["time_source"],
              "received_at": current["received_at"], "lines": payload["lines"],
              "accepted": current["attestations"][-1]["accepted"], "provenance": "REAL",
              "evidence_status": current["evidence_status"], "attachment_count": len(current["attachments"]),
              "purpose": grant.purpose, "notice": packet["notice"]}
    result["manifest_sha256"] = digest(result)
    db.add(ReceivingAudit(site_id=grant.site_id, actor_id="grant:" + grant.id, action="grant.accessed",
                          target=receipt.id, details={"revision": grant.revision}, at=now()))
    db.commit()
    return result


@router.get("/metrics")
def metrics(start: datetime, end: datetime, eligible_arrivals: int = Query(..., ge=1),
            register_reference: str = Query(..., min_length=3, max_length=200),
            actor=Depends(receiving_coordinator), db: Session = Depends(get_session)):
    if start.tzinfo is None or end.tzinfo is None or start >= end or end - start > timedelta(days=93):
        raise HTTPException(422, "Supply timezone-aware start/end, up to 93 days")
    recorded = confirmed = disputed = unmatched = 0
    for receipt in db.query(Receipt).filter_by(site_id=actor.site_id).all():
        packet = receipt_packet(db, receipt, history=False)["current"]
        payload = packet["payload"]
        observed = datetime.fromisoformat(payload["observed_at"].replace("Z", "+00:00"))
        if payload["provenance"] != "REAL" or not start <= observed < end:
            continue
        recorded += 1
        confirmed += int(packet["complete_confirmed"])
        disputed += int(packet["evidence_status"] == "disputed")
        unmatched += int(payload["plan_id"] is None)
    if recorded > eligible_arrivals:
        raise HTTPException(422, "Recorded receipts exceed independent arrivals; reconcile duplicates/denominator first")
    return {"start": start.isoformat(), "end": end.isoformat(), "evaluated_at": now().isoformat(),
            "site_id": actor.site_id, "eligible_arrivals": eligible_arrivals,
            "register_reference": register_reference, "recorded": recorded, "complete_confirmed": confirmed,
            "disputed": disputed, "unmatched": unmatched, "recorded_coverage": recorded / eligible_arrivals,
            "confirmed_coverage": confirmed / eligible_arrivals,
            "notice": "Denominator supplied by coordinator from independent register; physical-arrival deduplication must be reviewed. SIM excluded."}
