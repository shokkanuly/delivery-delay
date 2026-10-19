"""Push gate arrivals to SitePulse with an HMAC signature (the sender side of POST /integrations/gate-events).

Usage:
    SITEPULSE_KEY_ID=gate-1 SITEPULSE_KEY_SECRET=<32+ chars> \
    python scripts/send_gate_events.py http://127.0.0.1:8000 arrivals.csv

arrivals.csv columns: event_id,delivery_ref,occurred_on[,gate]  (occurred_on as YYYY-MM-DD).
A 1C receipt export or a gate scanner log can be converted to this CSV with a spreadsheet.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from api.signing import sign  # noqa: E402

PATH = "/integrations/gate-events"


def main(base_url: str, csv_path: str) -> None:
    with open(csv_path, encoding="utf-8-sig") as f:
        events = [{k: v for k, v in row.items() if v} for row in csv.DictReader(f)]
    body = json.dumps({"events": events}, ensure_ascii=False).encode()
    headers = sign(os.environ["SITEPULSE_KEY_ID"], os.environ["SITEPULSE_KEY_SECRET"], "POST", PATH, body)
    req = urllib.request.Request(base_url.rstrip("/") + PATH, data=body, method="POST",
                                 headers={**headers, "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        print(resp.read().decode())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
