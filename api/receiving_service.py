"""Transactional receiving helpers, separate from prediction outcomes and public reference data."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
import os

from fastapi import HTTPException
from sqlalchemy import update

from db.models import (ReceivingPlan, Receipt, ReceiptRevision, ReceiptAttachment,
                       ReceiptAttestation, ReceivingActor, ReceivingAudit)
from db.models import ReceivingNotification
from engines.receiving import digest, receipt_summary, reconciliation


def now():
    return datetime.now(timezone.utc)


def iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value.tzinfo is None else value.isoformat()


def audit(db, actor, action, target, details=None):
    db.add(ReceivingAudit(site_id=actor.site_id, actor_id=actor.id, action=action,
                          target=str(target), details=details or {}, at=now()))


def scoped(db, model, object_id, actor):
    row = db.query(model).filter_by(id=str(object_id), site_id=actor.site_id).first()
    if row is None:
        raise HTTPException(404, "Record not found")
    return row


def lock_receipt(db, receipt_id, actor):
    # UPDATE is a write lock on both supported databases. All receipt mutations use it.
    result = db.execute(update(Receipt).where(Receipt.id == str(receipt_id), Receipt.site_id == actor.site_id)
                        .values(mutation=Receipt.mutation + 1))
    if result.rowcount != 1:
        raise HTTPException(404, "Receipt not found")
    db.expire_all()
    return scoped(db, Receipt, receipt_id, actor)


def check_payload(db, payload, actor):
    if payload["plan_id"]:
        plan = scoped(db, ReceivingPlan, payload["plan_id"], actor)
        if plan.payload["provenance"] != payload["provenance"]:
            raise HTTPException(422, "Plan and receipt provenance must match")
        if plan.reference != payload["reference"]:
            raise HTTPException(422, "Reference must match the selected plan")
        # Unit/material differences may be real discrepancies; retain and display them.


def current_revision(db, receipt):
    return db.query(ReceiptRevision).filter_by(receipt_id=receipt.id, number=receipt.revision).one()


def make_revision(db, actor, receipt, operation_id, payload, request_digest, reason=None):
    row = ReceiptRevision(id=str(uuid4()), receipt_id=receipt.id, site_id=actor.site_id,
                          operation_id=str(operation_id), number=receipt.revision, payload=payload,
                          digest=digest(payload), request_digest=request_digest, actor_id=actor.id,
                          reason=reason, received_at=now())
    db.add(row)
    audit(db, actor, "receipt.recorded" if receipt.revision == 1 else "receipt.corrected",
          receipt.id, {"revision": receipt.revision, "digest": row.digest, "reason": reason})
    notify_coordinators(db, actor, "receipt:" + str(operation_id),
                        {"kind": "receipt", "receipt_id": receipt.id, "reference": payload["reference"],
                         "revision": receipt.revision})
    return row


def notify_coordinators(db, actor, event_key, payload):
    if os.getenv("SITEPULSE_ENABLE_OPERATIONS") != "1":
        return
    for recipient in db.query(ReceivingActor).filter_by(site_id=actor.site_id, role="coordinator", active=True).all():
        if recipient.id != actor.id:
            db.add(ReceivingNotification(id=str(uuid4()), site_id=actor.site_id, actor_id=recipient.id,
                                          event_key=event_key, payload=payload, created_at=now()))


def decision_for(db, revision):
    return (db.query(ReceiptAttestation).filter_by(revision_id=revision.id)
            .order_by(ReceiptAttestation.created_at.desc(), ReceiptAttestation.id.desc()).first())


def receipt_packet(db, receipt, history=True):
    revisions = (db.query(ReceiptRevision).filter_by(receipt_id=receipt.id)
                 .order_by(ReceiptRevision.number).all())
    current = next(r for r in revisions if r.number == receipt.revision)
    output = []
    for rev in revisions if history else [current]:
        files = (db.query(ReceiptAttachment.id, ReceiptAttachment.digest, ReceiptAttachment.content_type,
                          ReceiptAttachment.size, ReceiptAttachment.created_at)
                 .filter_by(revision_id=rev.id).order_by(ReceiptAttachment.id).all())
        attestations = (db.query(ReceiptAttestation).filter_by(revision_id=rev.id)
                        .order_by(ReceiptAttestation.created_at, ReceiptAttestation.id).all())
        actors = {r.id: r.name for r in db.query(ReceivingActor).filter(
            ReceivingActor.id.in_({rev.actor_id} | {a.actor_id for a in attestations})).all()}
        last = attestations[-1].payload if attestations else None
        summary = receipt_summary(rev.payload, last, len(files))
        plan = db.get(ReceivingPlan, rev.payload.get("plan_id")) if rev.payload.get("plan_id") else None
        summary["plan_comparison"] = reconciliation(plan.payload["lines"], rev.payload["lines"]) if plan else []
        summary["needs_review"] = (status_needs_review(summary) or rev.payload["condition"] != "ok"
                                   or any(x["status"] != "matched" for x in summary["plan_comparison"]))
        observed = datetime.fromisoformat(rev.payload["observed_at"].replace("Z", "+00:00"))
        delta = (datetime.fromisoformat(iso(rev.received_at)) - observed).total_seconds()
        summary["time_warning"] = "device_time_in_future" if delta < -300 else "late_sync_or_clock_difference" if delta > 3600 else None
        output.append({"number": rev.number, "payload": rev.payload, "digest": rev.digest,
                       "plan": {"id": plan.id, **plan.payload} if plan else None,
                       "received_at": iso(rev.received_at), "recorded_by": {"id": rev.actor_id, "name": actors.get(rev.actor_id)},
                       "reason": rev.reason, "superseded": rev.number != receipt.revision,
                       "attachments": [{"id": f.id, "sha256": f.digest, "content_type": f.content_type,
                                        "size": f.size, "uploaded_at": iso(f.created_at)} for f in files],
                       "attestations": [{"id": a.id, "actor_id": a.actor_id, "actor_name": actors.get(a.actor_id),
                                         "at": iso(a.created_at), **a.payload} for a in attestations],
                       **summary})
    current_output = next(r for r in output if r["number"] == receipt.revision)
    packet = {"schema_version": 1, "receipt_id": receipt.id, "site_id": receipt.site_id,
              "current_revision": receipt.revision, "current": current_output,
              "revisions": output, "notice": "Receiver attestation; not independent or legal certification."}
    packet["manifest_sha256"] = digest(packet)
    return packet


def status_needs_review(summary):
    return (summary["evidence_status"] != "confirmed" or summary["partial_acceptance"]
            or any(x != "real_provenance" for x in summary["missing"]))


def validate_acceptance(payload, decision):
    quantities = {x["line_id"]: Decimal(x["quantity"]) for x in payload["lines"]}
    accepted = {x["line_id"]: Decimal(x["quantity"]) for x in decision["accepted"]}
    if not set(accepted) <= set(quantities):
        raise HTTPException(422, "Accepted line is not in the receipt")
    if any(qty > quantities[key] for key, qty in accepted.items()):
        raise HTTPException(422, "Accepted quantity exceeds observed quantity")
    if decision["decision"] == "confirmed" and set(accepted) != set(quantities):
        raise HTTPException(422, "Account for every received line before confirming")
