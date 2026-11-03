"""Local operator provisioning. No browser receives the server's admin key."""
from __future__ import annotations

import argparse
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from db import database
from db.models import ReceivingActor, ReceivingSite, ReceivingAudit
from api.security import credential_hash


def provision(site_name, actor_name, role, site_id=None, timezone_name="Asia/Almaty"):
    ZoneInfo(timezone_name)
    database.init_db()
    key = "SP-" + secrets.token_urlsafe(32)
    timestamp = datetime.now(timezone.utc)
    with database.SessionLocal() as db:
        site = db.get(ReceivingSite, site_id) if site_id else None
        if site_id and site is None:
            raise ValueError("Unknown site ID")
        if site is None:
            site = ReceivingSite(id=str(uuid4()), name=site_name, timezone=timezone_name, created_at=timestamp)
            db.add(site)
            db.flush()
        actor = ReceivingActor(id=str(uuid4()), site_id=site.id, name=actor_name, role=role,
                               key_hash=credential_hash(key), active=True, created_at=timestamp)
        db.add(actor)
        db.add(ReceivingAudit(site_id=site.id, actor_id="local-operator", action="actor.provisioned",
                              target=actor.id, details={"role": role}, at=timestamp))
        db.commit()
        return {"site_id": site.id, "site_name": site.name, "actor_id": actor.id,
                "actor_name": actor.name, "role": role, "credential": key}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-name", default="SitePulse site")
    parser.add_argument("--site-id")
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", choices=["coordinator", "receiver", "viewer"], required=True)
    parser.add_argument("--timezone", default="Asia/Almaty")
    parser.add_argument("--output", required=True, help="New private file; will not overwrite an existing credential")
    args = parser.parse_args()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Reserve output before creating credentials; a typo cannot silently overwrite another actor.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        stream = os.fdopen(fd, "w")
        with stream:
            result = provision(args.site_name, args.name, args.role, args.site_id, args.timezone)
            json.dump(result, stream, ensure_ascii=False, indent=2)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    print(f"Named access saved to {path}. Transfer privately; do not commit this file.")


if __name__ == "__main__":
    main()
