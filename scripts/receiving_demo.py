"""Create a local SIM-only receiving rehearsal. Does not change an existing preview."""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from scripts.receiving_admin import provision
from db import database
from db.models import ReceivingPlan
from api.receiving_service import now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", default="var/receiving/preview-access.json")
    args = parser.parse_args()
    path = Path(args.credentials)
    if path.exists():
        print(f"Preview access already exists: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    actor = provision("Учебный объект · SitePulse", "Учебный координатор", "coordinator")
    today = datetime.now(ZoneInfo("Asia/Almaty")).date().isoformat()
    with database.SessionLocal() as db:
        for ref, supplier, material, quantity, unit in [
            ("DEMO-1042", "Учебный поставщик А", "Арматура А500", "10.25", "т"),
            ("DEMO-1043", "Учебный поставщик Б", "Цемент М500", "24", "т"),
            ("DEMO-1044", "Учебный поставщик В", "Кирпич", "1200", "шт"),
        ]:
            payload = {"reference": ref, "supplier": supplier, "promised_date": today,
                       "window_start": None, "window_end": None, "provenance": "SIM",
                       "lines": [{"line_id": "1", "material": material, "quantity": quantity, "unit": unit}]}
            db.add(ReceivingPlan(id=str(uuid4()), site_id=actor["site_id"], reference=ref, payload=payload,
                                  status="expected", created_by=actor["actor_id"], created_at=now()))
        db.commit()
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        json.dump(actor, stream, ensure_ascii=False, indent=2)
    print(f"SIM-only preview created. Named access is in {path}; never commit it.")


if __name__ == "__main__":
    main()
