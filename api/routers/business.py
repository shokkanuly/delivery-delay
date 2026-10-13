"""Business endpoints: economics (business/economics.py) and company workspaces.

  GET  /economics                    every pitch number and its assumptions
  POST /economics/site               stateless per-site finance for live what-ifs
  POST /projects/workspace           create (blank key -> server issues one) or update
  GET  /projects/workspace/{key}     read; finance is derived on every read

Workspaces are stored in the `workspaces` table (db/models.Workspace). Demo
workspaces are read-only, and GET never writes.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.schemas import CompanyWorkspaceIn, SiteInputsIn
from api.security import new_workspace_key
from business import economics
from db.database import get_session
from db.models import Workspace

router = APIRouter(tags=["business"])


@router.get("/economics")
def get_economics() -> dict:
    """Every pitch number (ROI scenarios, unit economics, forecast, market) and
    the assumptions behind it -- the same figures README and the deck quote."""
    return economics.summary()


@router.post("/economics/site")
def site_economics(site: SiteInputsIn) -> dict:
    """Stateless per-site finance for live what-if editing in the UIs."""
    return economics.site_finance(site.model_dump())


def _out(ws: Workspace) -> dict:
    inputs = dict(ws.inputs)
    return {"access_key": ws.access_key, **inputs, "read_only": ws.read_only,
            "finance": economics.site_finance(inputs)}


@router.post("/projects/workspace")
def save_company_workspace(ws_in: CompanyWorkspaceIn,
                           db: Session = Depends(get_session)) -> dict:
    data = ws_in.model_dump()
    key = data.pop("access_key").strip()
    if not key:
        ws = Workspace(access_key=new_workspace_key(), inputs=data, read_only=False)
        db.add(ws)
        status = "created"
    else:
        ws = db.get(Workspace, key)
        if ws is None:
            raise HTTPException(404, "Unknown access key. Save with a blank key to get a new one.")
        if ws.read_only:
            raise HTTPException(403, "Demo workspaces are read-only. Save with a blank key to get your own.")
        ws.inputs = data
        status = "saved"
    db.commit()
    db.refresh(ws)
    return {"status": status, "access_key": ws.access_key, "workspace": _out(ws)}


@router.get("/projects/workspace/{access_key}")
def get_company_workspace(access_key: str, db: Session = Depends(get_session)) -> dict:
    ws = db.get(Workspace, access_key.strip())
    if ws is None:
        raise HTTPException(404, "Workspace access key not found")
    return {"found": True, "workspace": _out(ws)}
