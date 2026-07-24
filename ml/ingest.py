"""Load & validate a real deliveries CSV into the canonical schema.

This is the seam for replacing synthetic data with actual BI Group exports.
Point the training / seeding paths at a file:
    ml.train.load_training_frame(csv_path="deliveries.csv")
    db.seed.seed(csv_path="deliveries.csv")
or validate a file directly:
    python3 -m ml.ingest deliveries.csv

Canonical columns (see sample_deliveries.csv):
    supplier_id, project_site, material_type, route_type, quantity,
    order_date, promised_date, actual_date
`actual_date` and `project_site` are optional for scoring-only files; actual_date
is required for training/seeding (it's needed to build the late/on-time label).
"""
from __future__ import annotations

import pandas as pd

CANONICAL_COLUMNS = ["supplier_id", "project_site", "material_type", "route_type",
                     "quantity", "order_date", "promised_date", "actual_date"]
CORE_REQUIRED = ["supplier_id", "material_type", "route_type", "quantity",
                 "order_date", "promised_date"]
DATE_COLUMNS = ["order_date", "promised_date", "actual_date"]


class DeliveryCSVError(ValueError):
    """Raised when a deliveries CSV is structurally unusable."""


def load_deliveries_csv(source, *, require_actual: bool = True) -> pd.DataFrame:
    """Return a validated, canonical deliveries DataFrame.

    - `source`: a path/file-like, or an already-loaded DataFrame.
    - `require_actual=True` (default) demands `actual_date` (needed for labels in
      training/seeding). Use False for scoring-only files (future deliveries).

    Raises DeliveryCSVError on missing columns or if nothing valid remains;
    silently drops individual bad rows and prints a one-line report.
    """
    df = source.copy() if isinstance(source, pd.DataFrame) else pd.read_csv(source)
    df.columns = [c.strip().lower() for c in df.columns]

    required = list(CORE_REQUIRED) + (["actual_date"] if require_actual else [])
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise DeliveryCSVError(
            f"CSV missing required columns: {missing}. Expected at least {required}."
        )

    n0 = len(df)
    if "project_site" not in df.columns:
        df["project_site"] = "unknown"

    for col in [c for c in DATE_COLUMNS if c in df.columns]:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")

    before = len(df)
    df = df.dropna(subset=required)
    df = df[df["quantity"] > 0]
    dropped = before - len(df)

    if df.empty:
        raise DeliveryCSVError(
            f"No valid rows after validation (started with {n0}). "
            "Check date formats and that quantity is a positive number."
        )

    bad_promise = int((df["promised_date"] < df["order_date"]).sum())
    keep = [c for c in CANONICAL_COLUMNS if c in df.columns]
    df = df[keep].reset_index(drop=True)

    report = f"[ingest] kept {len(df)}/{n0} rows"
    if dropped:
        report += f"; dropped {dropped} invalid (bad date/quantity/missing field)"
    if bad_promise:
        report += f"; {bad_promise} rows have promised_date < order_date (kept, flagged)"
    print(report)
    return df


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("usage: python3 -m ml.ingest <deliveries.csv> [--no-actual]")
        raise SystemExit(1)
    require_actual = "--no-actual" not in sys.argv
    out = load_deliveries_csv(sys.argv[1], require_actual=require_actual)
    print(out.head(10).to_string(index=False))
    print(f"columns: {list(out.columns)}")
