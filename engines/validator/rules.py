"""Construction-sequencing validation.

Flags deliveries that arrive out of step with the build programme. Two rules:

  R1 premature_delivery  -- delivery_date < phase_start_date.
     Material shows up before the phase that needs it has begun: it occupies
     site storage, is exposed to weather and theft, and blocks access.

  R2 material_phase_mismatch -- material_type is not in the phase's allowed list
     (from phase_material_map.csv). Cannot fire on the synthetic data (which is
     valid by construction) but is essential for real data, where a mis-keyed
     phase is a common data-entry error. Kept, and reported separately, so it
     never inflates the R1 accuracy numbers.

The engine is deterministic, so validating it is a CORRECTNESS check on the date
logic, not a modelling exercise -- `evaluate_against_truth` scores it against the
ground-truth `flag` column, which is never an input to the rules.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

PREMATURE = "premature_delivery"
MISMATCH = "material_phase_mismatch"
REQUIRED_COLUMNS = ["project_id", "material_type", "required_phase", "delivery_date"]


@dataclass
class ValidationSummary:
    rows: list[dict]
    counts: dict
    metrics: dict | None = None


def load_phase_material_map(source) -> dict[str, set[str]]:
    """phase_name -> allowed materials (the CSV stores them semicolon-separated).

    A phase with no listed materials (blank/NaN, e.g. `handover`) maps to an
    EMPTY set, which R2 treats as *unconstrained* rather than "forbid everything".
    An unspecified allowlist means the phase simply isn't restricted; reading it
    as a deny-all would flag every delivery in that phase.
    """
    df = source if isinstance(source, pd.DataFrame) else pd.read_csv(source)
    out: dict[str, set[str]] = {}
    for _, r in df.iterrows():
        raw = r["required_materials"]
        materials = set() if pd.isna(raw) else {
            m.strip() for m in str(raw).split(";") if m.strip()
        }
        out[str(r["phase_name"])] = materials
    return out


def _phase_windows(build_phases: pd.DataFrame) -> dict[tuple[str, str], tuple]:
    """(project_id, phase_name) -> (start, end) from the build programme."""
    bp = build_phases.copy()
    bp["start_date"] = pd.to_datetime(bp["start_date"])
    bp["end_date"] = pd.to_datetime(bp["end_date"])
    return {(r["project_id"], r["phase_name"]): (r["start_date"], r["end_date"])
            for _, r in bp.iterrows()}


def validate_deliveries(
    deliveries: pd.DataFrame,
    phase_map: dict[str, set[str]] | None = None,
    build_phases: pd.DataFrame | None = None,
) -> ValidationSummary:
    """Annotate each delivery with `predicted_flag` and a human-readable `reason`.

    Phase windows come from `build_phases` when supplied (the real-world path,
    where the schedule lives in the DB); otherwise from the phase_start_date /
    phase_end_date columns carried on the delivery rows themselves.
    """
    df = deliveries.copy()
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"deliveries missing required columns: {missing}")

    for col in ("delivery_date", "phase_start_date", "phase_end_date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    windows = _phase_windows(build_phases) if build_phases is not None else {}

    rows = []
    for _, d in df.iterrows():
        start, end = windows.get((d["project_id"], d["required_phase"]), (None, None))
        if start is None:
            start = d.get("phase_start_date")
            end = d.get("phase_end_date")

        flag, reason = None, "in sequence"

        if pd.notna(d["delivery_date"]) and pd.notna(start) and d["delivery_date"] < start:
            days = int((start - d["delivery_date"]).days)
            flag = PREMATURE
            reason = (f"arrives {days} day(s) before '{d['required_phase']}' starts "
                      f"({start.date()}) — early site storage / access risk")
        elif phase_map is not None:
            allowed = phase_map.get(str(d["required_phase"]))
            if allowed and d["material_type"] not in allowed:
                flag = MISMATCH
                reason = (f"'{d['material_type']}' is not a listed material for phase "
                          f"'{d['required_phase']}' — check the phase on this order")

        row = d.to_dict()
        row["predicted_flag"] = flag
        row["reason"] = reason
        rows.append(row)

    counts = {
        "total": len(rows),
        PREMATURE: sum(r["predicted_flag"] == PREMATURE for r in rows),
        MISMATCH: sum(r["predicted_flag"] == MISMATCH for r in rows),
        "clean": sum(r["predicted_flag"] is None for r in rows),
    }
    return ValidationSummary(rows=rows, counts=counts)


def evaluate_against_truth(summary: ValidationSummary, truth_column: str = "flag") -> dict:
    """Precision / recall of R1 against the ground-truth flag column."""
    df = pd.DataFrame(summary.rows)
    if truth_column not in df.columns:
        return {}
    truth = df[truth_column].fillna("").eq(PREMATURE)
    pred = df["predicted_flag"].fillna("").eq(PREMATURE)
    tp = int((truth & pred).sum())
    fp = int((~truth & pred).sum())
    fn = int((truth & ~pred).sum())
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"true_positives": tp, "false_positives": fp, "false_negatives": fn,
            "precision": round(precision, 4), "recall": round(recall, 4),
            "f1": round(f1, 4)}
