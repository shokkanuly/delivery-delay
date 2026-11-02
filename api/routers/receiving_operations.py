"""Optional human-approved slots, in-app notifications and field-only supplier observations."""
from datetime import datetime, timezone
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import update
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from api.security import receiving_actor, receiving_writer, receiving_coordinator
from api.schemas import ReceivingResourceIn, ReceivingSlotIn, ReceivingSlotDecisionIn
from api.receiving_service import audit, iso, now, scoped, receipt_packet, notify_coordinators
from api.routers.receiving import feature
from db.database import get_session
from db.models import (ReceivingResource, ReceivingSlot, ReceivingPlan, ReceivingNotification,
                       ReceivingSite, Receipt)
from engines.receiving import digest
from ml.scorecard import wilson_interval

router = APIRouter(prefix="/receiving", tags=["receiving-operations"])


def enabled():
    feature("SITEPULSE_ENABLE_OPERATIONS")


def slot_out(slot):
    return {"id": slot.id, "resource_id": slot.resource_id, "plan_id": slot.plan_id,
            "start_at": iso(slot.start_at), "end_at": iso(slot.end_at), "status": slot.status,
            "version": slot.version, "requested_by": slot.actor_id}


@router.post("/resources", dependencies=[Depends(enabled)], status_code=201)
def resource(body: ReceivingResourceIn, actor=Depends(receiving_coordinator), db: Session = Depends(get_session)):
    row = ReceivingResource(id=str(uuid4()), site_id=actor.site_id, name=body.name, kind=body.kind, mutation=0)
    db.add(row)
    audit(db, actor, "resource.created", row.id, {"name": body.name})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Physical resource name already registered at this site")
    return {"id": row.id, "name": row.name, "kind": row.kind}


@router.get("/resources", dependencies=[Depends(enabled)])
def resources(actor=Depends(receiving_actor), db: Session = Depends(get_session)):
    return {"resources": [{"id": r.id, "name": r.name, "kind": r.kind}
            for r in db.query(ReceivingResource).filter_by(site_id=actor.site_id).order_by(ReceivingResource.name).limit(200).all()]}


@router.post("/slots", dependencies=[Depends(enabled)], status_code=201)
def request_slot(body: ReceivingSlotIn, actor=Depends(receiving_writer), db: Session = Depends(get_session)):
    scoped(db, ReceivingResource, body.resource_id, actor)
    if body.plan_id:
        scoped(db, ReceivingPlan, body.plan_id, actor)
    fingerprint = digest(body.model_dump(mode="json"))
    row = ReceivingSlot(id=str(body.slot_id), site_id=actor.site_id, resource_id=str(body.resource_id),
                        plan_id=str(body.plan_id) if body.plan_id else None,
                        start_at=body.start_at.astimezone(timezone.utc), end_at=body.end_at.astimezone(timezone.utc),
                        status="requested", version=1, actor_id=actor.id, request_digest=fingerprint, created_at=now())
    db.add(row)
    audit(db, actor, "slot.requested", row.id)
    notify_coordinators(db, actor, "slot:" + row.id, {"kind": "slot_requested", "slot_id": row.id})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        old = db.get(ReceivingSlot, str(body.slot_id))
        if old and old.site_id == actor.site_id and old.actor_id == actor.id and old.request_digest == fingerprint:
            return slot_out(old)
        raise HTTPException(409, "Slot ID conflict")
    return slot_out(row)


@router.get("/slots", dependencies=[Depends(enabled)])
def slots(limit: int = Query(100, ge=1, le=200), actor=Depends(receiving_actor), db: Session = Depends(get_session)):
    return {"slots": [slot_out(r) for r in db.query(ReceivingSlot).filter_by(site_id=actor.site_id)
            .order_by(ReceivingSlot.start_at.desc()).limit(limit).all()]}


@router.post("/slots/{slot_id}/decision", dependencies=[Depends(enabled)])
def decide_slot(slot_id: UUID, body: ReceivingSlotDecisionIn, actor=Depends(receiving_coordinator),
                db: Session = Depends(get_session)):
    row = scoped(db, ReceivingSlot, slot_id, actor)
    # Serialize approval/movement on this physical resource, including concurrent requests.
    db.execute(update(ReceivingResource).where(ReceivingResource.id == row.resource_id,
                                              ReceivingResource.site_id == actor.site_id)
               .values(mutation=ReceivingResource.mutation + 1))
    db.expire_all()
    row = scoped(db, ReceivingSlot, slot_id, actor)
    allowed = {"requested": {"approve", "reject", "cancel", "move"}, "approved": {"move", "cancel"}}
    if row.version != body.expected_version or body.action not in allowed.get(row.status, set()):
        raise HTTPException(409, "Slot changed or transition is not allowed")
    if body.action == "move":
        row.start_at = body.start_at.astimezone(timezone.utc)
        row.end_at = body.end_at.astimezone(timezone.utc)
    if body.action == "approve" or (body.action == "move" and row.status == "approved"):
        overlap = (db.query(ReceivingSlot.id).filter(ReceivingSlot.site_id == actor.site_id,
                   ReceivingSlot.resource_id == row.resource_id, ReceivingSlot.id != row.id,
                   ReceivingSlot.status == "approved", ReceivingSlot.start_at < row.end_at,
                   ReceivingSlot.end_at > row.start_at).first())
        if overlap:
            raise HTTPException(409, "Physical resource already approved for an overlapping slot")
    row.status = {"approve": "approved", "reject": "rejected", "cancel": "cancelled"}.get(body.action, row.status)
    row.version += 1
    audit(db, actor, "slot." + body.action, row.id,
          {"reason": body.reason, "version": row.version, "start_at": iso(row.start_at), "end_at": iso(row.end_at)})
    if row.actor_id != actor.id:
        db.add(ReceivingNotification(id=str(uuid4()), site_id=actor.site_id, actor_id=row.actor_id,
                                      event_key=f"slot-decision:{row.id}:{row.version}",
                                      payload={"kind": "slot_decision", "slot_id": row.id, "status": row.status}, created_at=now()))
    db.commit()
    return slot_out(row)


@router.get("/notifications", dependencies=[Depends(enabled)])
def notifications(actor=Depends(receiving_actor), db: Session = Depends(get_session)):
    query = db.query(ReceivingNotification).filter_by(site_id=actor.site_id, actor_id=actor.id)
    return {"unread": query.filter(ReceivingNotification.read_at.is_(None)).count(),
            "notifications": [{"id": n.id, "payload": n.payload, "read": n.read_at is not None, "at": iso(n.created_at)}
                              for n in query.order_by(ReceivingNotification.created_at.desc()).limit(100).all()]}


@router.post("/notifications/{notification_id}/read", dependencies=[Depends(enabled)])
def read_notification(notification_id: UUID, actor=Depends(receiving_actor), db: Session = Depends(get_session)):
    row = scoped(db, ReceivingNotification, notification_id, actor)
    if row.actor_id != actor.id:
        raise HTTPException(404, "Notification not found")
    row.read_at = now()
    db.commit()
    return {"read": True}


@router.get("/supplier-history", dependencies=[Depends(enabled)])
def supplier_history(actor=Depends(receiving_actor), db: Session = Depends(get_session)):
    site = db.get(ReceivingSite, actor.site_id)
    zone = ZoneInfo(site.timezone)
    groups = {}
    for receipt in db.query(Receipt).filter_by(site_id=actor.site_id).all():
        current = receipt_packet(db, receipt, history=False)["current"]
        if not current["complete_confirmed"]:
            continue
        p = current["payload"]
        plan = scoped(db, ReceivingPlan, p["plan_id"], actor)
        arrival = datetime.fromisoformat(p["observed_at"].replace("Z", "+00:00"))
        if plan.payload["window_end"]:
            on_time = arrival <= datetime.fromisoformat(plan.payload["window_end"].replace("Z", "+00:00"))
        else:
            on_time = arrival.astimezone(zone).date().isoformat() <= plan.payload["promised_date"]
        group = groups.setdefault(plan.payload["supplier"], {"receipts": 0, "on_time": 0})
        group["receipts"] += 1
        group["on_time"] += int(on_time)
    rows = []
    for supplier, data in groups.items():
        low, high = wilson_interval(data["on_time"], data["receipts"])
        rows.append({"supplier": supplier, **data, "on_time_share": data["on_time"] / data["receipts"],
                     "ci_low": low, "ci_high": high})
    return {"suppliers": rows, "notice": "Within-site, complete confirmed REAL receipts only. Receipt-level arrival vs promise; not the ML material-grace label, fault attribution or a credit score."}
