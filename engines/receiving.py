"""Pure evidence rules. Device claims and confirmations never become independent proof."""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal


def digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def receipt_summary(payload: dict, decision: dict | None, attachment_count: int) -> dict:
    status = decision["decision"] if decision else "recorded"
    missing = []
    if not payload.get("plan_id"):
        missing.append("delivery_match")
    if not attachment_count:
        missing.append("attachment")
    if status != "confirmed":
        missing.append("receiver_confirmation")
    if payload.get("provenance") != "REAL":
        missing.append("real_provenance")
    accepted = {x["line_id"]: Decimal(x["quantity"]) for x in (decision or {}).get("accepted", [])}
    partial = any(accepted.get(x["line_id"], Decimal(0)) < Decimal(x["quantity"])
                  for x in payload["lines"]) if decision else False
    return {"evidence_status": status, "missing": missing,
            "complete_confirmed": not missing, "partial_acceptance": partial,
            "location_available": payload.get("location") is not None}


def reconciliation(lines: list[dict], received: list[dict]) -> list[dict]:
    """Exact line/material/unit comparison; never silently convert units or fuzzy-match."""
    result = []
    by_id = {line["line_id"]: line for line in received}
    ambiguous = {line["line_id"] for line in received
                 if sum(x["line_id"] == line["line_id"] for x in received) > 1}
    for line in lines:
        other = by_id.get(line["line_id"])
        if line["line_id"] in ambiguous:
            status = "ambiguous_receipt_lines"
        elif other is None:
            status = "unmatched"
        elif (line["material"], line["unit"]) != (other["material"], other["unit"]):
            status = "material_or_unit_mismatch"
        elif Decimal(line["quantity"]) != Decimal(other["quantity"]):
            status = "quantity_mismatch"
        else:
            status = "matched"
        result.append({"line_id": line["line_id"], "status": status,
                       "declared_quantity": line["quantity"],
                       "received_quantity": other["quantity"] if other else None})
    for line in received:
        if line["line_id"] not in {x["line_id"] for x in lines}:
            result.append({"line_id": line["line_id"], "status": "missing_document_line",
                           "declared_quantity": None, "received_quantity": line["quantity"]})
    return result


def plan_progress(planned_lines: list[dict], receipts: list[dict]) -> dict:
    """Sum current receipts by exact line/material/unit; confirmed quantities alone fulfil a plan."""
    expected = {(x['line_id'], x['material'], x['unit']): x for x in planned_lines}
    totals = {key: [Decimal(0), Decimal(0)] for key in expected}
    pending = 0
    for receipt in receipts:
        decision = receipt.get('decision')
        confirmed = decision is not None and decision['decision'] == 'confirmed'
        pending += int(not confirmed)
        accepted = {x['line_id']: Decimal(x['quantity']) for x in decision['accepted']} if confirmed else {}
        for line in receipt['payload']['lines']:
            key = (line['line_id'], line['material'], line['unit'])
            values = totals.setdefault(key, [Decimal(0), Decimal(0)])
            values[0] += Decimal(line['quantity'])
            values[1] += accepted.get(line['line_id'], Decimal(0))
    rows = []
    for key, (observed, accepted) in totals.items():
        planned = Decimal(expected[key]['quantity']) if key in expected else None
        status = ('unexpected_material_or_unit' if planned is None else 'matched' if accepted == planned
                  else 'over_accepted' if accepted > planned else 'partial' if accepted > 0 else 'not_accepted')
        rows.append({'line_id': key[0], 'material': key[1], 'unit': key[2],
                     'planned_quantity': str(planned) if planned is not None else None,
                     'observed_quantity': str(observed), 'accepted_quantity': str(accepted),
                     'remaining_quantity': str(max(planned - accepted, Decimal(0))) if planned is not None else None,
                     'status': status})
    return {'lines': rows, 'receipt_count': len(receipts), 'pending_receipts': pending,
            'quantities_match': all(row['status'] == 'matched' for row in rows),
            'notice': 'Current revisions only. Acceptance requires a confirmed decision. Units/materials are never converted; matching totals do not automatically close a plan.'}
