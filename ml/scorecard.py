"""Historical supplier reliability, with the same material grace as model labels.

This describes completed deliveries; it is not a prediction. Delay quantiles
cover late deliveries only, measured from the promised date (not after grace).
The recent window is the last 90 calendar days ending on the latest arrival in
the entire export, so every supplier is compared over the same observed period.
"""
from __future__ import annotations

import math
from statistics import NormalDist

import pandas as pd

from ml.labeling import LabelConfig, add_labels

_METRICS = [
    "deliveries", "on_time", "late", "on_time_share", "on_time_ci_low", "on_time_ci_high",
    "median_late_days", "p90_late_days", "recent_deliveries", "previous_deliveries",
    "recent_on_time_share", "previous_on_time_share", "trend_pp",
]


def wilson_interval(on_time: int, total: int) -> tuple[float | None, float | None]:
    """Two-sided Wilson 95% interval; no observations means no estimate."""
    if total < 0 or on_time < 0 or on_time > total or int(total) != total or int(on_time) != on_time:
        raise ValueError("Counts must be integers with 0 <= on_time <= total")
    if total == 0:
        return None, None
    z = NormalDist().inv_cdf(0.975)
    p = on_time / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, center - half), min(1.0, center + half)


def _history(df: pd.DataFrame) -> pd.DataFrame:
    required = ["supplier_id", "material_type", "promised_date", "actual_date"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError("Missing scorecard columns: " + ", ".join(missing))
    out = df.copy()
    if out[["supplier_id", "material_type"]].isna().any().any():
        raise ValueError("Supplier and material must be present on every delivery")
    for col in ("promised_date", "actual_date"):
        out[col] = pd.to_datetime(out[col], errors="raise")
        if out[col].isna().any():
            raise ValueError("Scorecards require completed deliveries with valid dates")
    if out.empty:
        return out
    # Recompute rather than trusting a caller's possibly stale is_late column.
    return add_labels(out, LabelConfig())


def _scorecard(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    history = _history(df)
    columns = keys + _METRICS
    if history.empty:
        return pd.DataFrame(columns=columns)
    # Inclusive 90-day window: the latest arrival plus its 89 preceding days.
    cutoff = history["actual_date"].max().normalize() - pd.Timedelta(days=89)
    rows = []
    for key, group in history.groupby(keys, sort=True, observed=True):
        values = key if isinstance(key, tuple) else (key,)
        n = len(group)
        late = group[group["is_late"] == 1]
        on_time = n - len(late)
        lower, upper = wilson_interval(on_time, n)
        recent = group[group["actual_date"] >= cutoff]
        previous = group[group["actual_date"] < cutoff]
        recent_share = float(1 - recent["is_late"].mean()) if len(recent) else None
        previous_share = float(1 - previous["is_late"].mean()) if len(previous) else None
        rows.append({
            **dict(zip(keys, values)),
            "deliveries": n, "on_time": on_time, "late": len(late), "on_time_share": on_time / n,
            "on_time_ci_low": lower, "on_time_ci_high": upper,
            "median_late_days": float(late["delay_days"].median()) if len(late) else None,
            "p90_late_days": float(late["delay_days"].quantile(0.9)) if len(late) else None,
            "recent_deliveries": len(recent), "previous_deliveries": len(previous),
            "recent_on_time_share": recent_share, "previous_on_time_share": previous_share,
            "trend_pp": 100 * (recent_share - previous_share)
            if recent_share is not None and previous_share is not None else None,
        })
    return pd.DataFrame(rows, columns=columns)


def supplier_scorecard(df: pd.DataFrame) -> pd.DataFrame:
    """One row per supplier; positive trend_pp means improved on-time share."""
    return _scorecard(df, ["supplier_id"])


def material_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """One row per supplier/material pair, using the same global recent window."""
    return _scorecard(df, ["supplier_id", "material_type"])
