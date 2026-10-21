"""Rebuild the public synthetic report: python -m scripts.build_demo_report [--check]."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ml.audit import build_audit_report
from ml.ingest import load_export

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "static/samples/1c_export_synthetic.csv"
TARGET = ROOT / "static/samples/audit_report_synthetic.json"


def demo_snapshot() -> dict:
    """A reproducible report tied to the exact downloadable synthetic bytes."""
    raw = SOURCE.read_bytes()
    frame, quality = load_export(raw)
    return {"format_version": 1, "source_file": SOURCE.name,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "report": build_audit_report(frame, quality, synthetic=True)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail when the committed sample is stale.")
    args = parser.parse_args()
    expected = json.dumps(demo_snapshot(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != expected:
            parser.exit(1, "Synthetic report is stale; run python -m scripts.build_demo_report\n")
        print("Synthetic report matches the downloadable CSV and current audit rules.")
    else:
        TARGET.write_text(expected, encoding="utf-8")
        print(f"Built {TARGET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
