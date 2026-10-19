"""Load & validate a real deliveries CSV into the canonical schema.

This is the seam for replacing synthetic data with a holding's real 1C/ERP exports.
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

A customer's actual export rarely arrives in this shape: it's a 1C or Excel
dump with Russian headers, `;`-delimited, often cp1251, dates as dd.mm.yyyy,
and numbers with space thousand separators. `load_export()` is that seam --
`COLUMN_PROFILE` maps known header aliases to the canonical columns, and
every row dropped or defaulted is counted in the returned `QualityReport`
(CLAUDE.md rule 6: a missing input is an error or a reported default, never
a silent one). `load_deliveries_csv()` above is unchanged and keeps serving
`ml.train`/`db.seed`, which already receive canonical headers.
"""
from __future__ import annotations

import csv as _csv
import io
import pathlib
from dataclasses import dataclass, field

import pandas as pd

CANONICAL_COLUMNS = ["supplier_id", "project_site", "material_type", "route_type",
                     "quantity", "distance_km", "order_date", "promised_date",
                     "actual_date"]
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


# ─── 1C / Excel export import (Stage 1, docs/plans/mvp-reshape.md D3) ───────

# canonical column -> accepted header aliases. Matched case-insensitively,
# stripped. Includes the canonical English name itself, so a file that
# already uses canonical headers (e.g. a re-export) still loads.
COLUMN_PROFILE: dict[str, list[str]] = {
    "supplier_id": ["Поставщик", "Контрагент", "supplier_id", "supplier"],
    "material_type": ["Номенклатура", "Материал", "material_type", "material"],
    "order_date": ["Дата заказа", "order_date"],
    "promised_date": ["Плановая дата поставки", "Срок", "Плановая дата", "promised_date"],
    "actual_date": ["Дата поступления", "Дата прихода", "actual_date"],
    "quantity": ["Количество", "quantity"],
}

# route_type has no 1C equivalent -- deliberately NOT in COLUMN_PROFILE. It is
# always defaulted to "unknown" by load_export(), and the default is counted
# in QualityReport.route_type_defaulted, never silently treated as real data.

_REQUIRED_CORE = ["supplier_id", "material_type", "quantity", "order_date", "promised_date"]
_NBSP_CHARS = ("\xa0", " ")  # non-breaking / thin space: 1C's thousand separators


def sniff_csv(raw: bytes) -> tuple[str, str]:
    """Decode a 1C/Excel export of unknown encoding and detect its delimiter.

    Tries utf-8-sig first (what Excel's "CSV UTF-8" export produces), then
    plain utf-8, then falls back to cp1251 -- every byte value is valid
    cp1251, so it never raises; it's the deliberate last resort, not a guess.
    Delimiter detection uses the stdlib `csv.Sniffer` over `,`, `;`, tab.
    """
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("cp1251")

    sample = text[:4096]
    try:
        delimiter = _csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
    except _csv.Error:
        delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    return text, delimiter


@dataclass
class QualityReport:
    """What happened to a 1C export on the way to the canonical frame. Every
    count here is a row (or file-wide) fact the caller can show a customer,
    so "does it work on our data" has an honest, specific answer."""

    rows_total: int
    rows_kept: int
    bad_dates: int = 0
    bad_quantity: int = 0
    duplicates: int = 0
    promised_before_order: int = 0
    route_type_defaulted: int = 0
    unmapped_columns: list[str] = field(default_factory=list)

    @property
    def rows_dropped(self) -> int:
        return self.rows_total - self.rows_kept

    def summary(self) -> str:
        lines = [f"kept {self.rows_kept}/{self.rows_total} rows"]
        if self.bad_dates:
            lines.append(f"{self.bad_dates} row(s) with an unparseable required date (dropped)")
        if self.bad_quantity:
            lines.append(f"{self.bad_quantity} row(s) with an invalid quantity (dropped)")
        if self.duplicates:
            lines.append(f"{self.duplicates} duplicate row(s) removed")
        if self.promised_before_order:
            lines.append(f"{self.promised_before_order} row(s) have promised_date before "
                         "order_date (kept, flagged)")
        if self.route_type_defaulted:
            lines.append("route_type is not in this export -- defaulted to 'unknown' for "
                         f"{self.route_type_defaulted} row(s)")
        if self.unmapped_columns:
            lines.append(f"{len(self.unmapped_columns)} column(s) not recognised and ignored: "
                         f"{self.unmapped_columns}")
        return "; ".join(lines)


def _ru_display_name(canonical: str, profile: dict[str, list[str]]) -> str:
    """The Russian header name(s) for a canonical column, for a missing-column
    error a Kazakhstani operator reading their own file can act on."""
    ru = [a for a in profile.get(canonical, []) if any("а" <= ch.lower() <= "я" for ch in a)]
    return (" / ".join(ru) + f" ({canonical})") if ru else canonical


def _clean_quantity(value) -> object:
    if pd.isna(value):
        return value
    cleaned = str(value)
    for ch in _NBSP_CHARS + (" ",):
        cleaned = cleaned.replace(ch, "")
    return cleaned


def load_export(
    raw: bytes | str | pathlib.Path,
    profile: dict[str, list[str]] | None = None,
    *,
    require_actual: bool = True,
) -> tuple[pd.DataFrame, QualityReport]:
    """Turn a raw 1C/Excel export into the canonical delivery frame, with a
    report of exactly what was dropped or defaulted and why.

    `raw` is the file's raw bytes (e.g. from an uploaded file), or a path to
    read them from. Raises DeliveryCSVError, with the Russian header names,
    if a required column cannot be found at all.
    """
    profile = profile or COLUMN_PROFILE
    if isinstance(raw, (str, pathlib.Path)):
        raw = pathlib.Path(raw).read_bytes()
    text, delimiter = sniff_csv(raw)
    df = pd.read_csv(io.StringIO(text), sep=delimiter, dtype=str)

    alias_to_canonical = {
        alias.strip().lower(): canonical
        for canonical, aliases in profile.items()
        for alias in aliases
    }
    rename, unmapped = {}, []
    for col in df.columns:
        canonical = alias_to_canonical.get(col.strip().lower())
        if canonical:
            rename[col] = canonical
        else:
            unmapped.append(col)
    df = df.rename(columns=rename)

    required = list(_REQUIRED_CORE) + (["actual_date"] if require_actual else [])
    missing = [c for c in required if c not in df.columns]
    if missing:
        names = ", ".join(_ru_display_name(c, profile) for c in missing)
        raise DeliveryCSVError(f"В файле не найдены обязательные столбцы: {names}.")

    n0 = len(df)
    if "project_site" not in df.columns:
        df["project_site"] = "unknown"  # same silent default as load_deliveries_csv

    route_type_defaulted = n0
    df["route_type"] = "unknown"

    bad_dates = 0
    for col in [c for c in DATE_COLUMNS if c in df.columns]:
        before_na = int(df[col].isna().sum())
        df[col] = pd.to_datetime(df[col].astype(str).str.strip(), dayfirst=True, errors="coerce")
        bad_dates += int(df[col].isna().sum()) - before_na

    before_qty_na = int(df["quantity"].isna().sum())
    df["quantity"] = pd.to_numeric(df["quantity"].map(_clean_quantity), errors="coerce")
    bad_quantity = int(df["quantity"].isna().sum()) - before_qty_na

    dup_subset = [c for c in ("supplier_id", "material_type", "quantity",
                              "order_date", "promised_date", "actual_date") if c in df.columns]
    dup_mask = df.duplicated(subset=dup_subset, keep="first")
    duplicates = int(dup_mask.sum())
    df = df[~dup_mask]

    df = df.dropna(subset=required)
    df = df[df["quantity"] > 0]

    if df.empty:
        raise DeliveryCSVError(
            f"No valid rows after validation (started with {n0}). "
            "Check date formats and that quantity is a positive number."
        )

    promised_before_order = int((df["promised_date"] < df["order_date"]).sum())
    keep = [c for c in CANONICAL_COLUMNS if c in df.columns]
    df = df[keep].reset_index(drop=True)

    report = QualityReport(
        rows_total=n0,
        rows_kept=len(df),
        bad_dates=bad_dates,
        bad_quantity=bad_quantity,
        duplicates=duplicates,
        promised_before_order=promised_before_order,
        route_type_defaulted=route_type_defaulted,
        unmapped_columns=unmapped,
    )
    return df, report


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("usage: python3 -m ml.ingest <deliveries.csv> [--no-actual]")
        raise SystemExit(1)
    require_actual = "--no-actual" not in sys.argv
    out = load_deliveries_csv(sys.argv[1], require_actual=require_actual)
    print(out.head(10).to_string(index=False))
    print(f"columns: {list(out.columns)}")
