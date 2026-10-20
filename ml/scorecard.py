"""Stage 2 (docs/plans/mvp-reshape.md D4): the supplier on-time scorecard --
the first sellable output, sold ahead of the ML model.

Lateness is computed by `ml.labeling.add_labels()`, the SAME per-material
grace window used everywhere else in the platform (the delay-risk model,
`/accuracy`). A supplier's "late" here means exactly what it means there --
never a second, scorecard-only definition of lateness.

Pure, framework-free (tests/test_layering.py). Input is a canonical
deliveries DataFrame with `actual_date` populated (ml.ingest's output shape,
or db-sourced equivalent); output is plain pandas DataFrames.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ml.labeling import LabelConfig, add_labels

# "Trend" = on-time share in the most recent N days of promised_date vs.
# everything before that cutoff. 90 days matches the plan's pilot cadence
# (D4) -- long enough to not be noise at one-site volume, short enough to
# catch a supplier's performance actually changing.
TREND_WINDOW_DAYS = 90


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (default z=1.96, 95%).

    Chosen over a normal-approximation interval because it stays inside
    [0, 1] and doesn't collapse to a point at p=0 or p=1 -- exactly the
    small-n regime a single supplier at a one-site pilot will be in.
    n=0 returns (0.0, 1.0): no deliveries, no evidence, maximum uncertainty.
    """
    if n <= 0:
        return (0.0, 1.0)
    phat = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    centre = phat + z2 / (2 * n)
    margin = z * np.sqrt((phat * (1 - phat) + z2 / (4 * n)) / n)
    lo = (centre - margin) / denom
    hi = (centre + margin) / denom
    return (max(0.0, lo), min(1.0, hi))


def _rollup(group: pd.DataFrame, cutoff: pd.Timestamp) -> dict:
    """One scorecard row's metrics for a single supplier (or supplier x
    material) group that already has `is_late` and `delay_days`."""
    n = len(group)
    on_time_n = int((group["is_late"] == 0).sum())
    lo, hi = wilson_interval(on_time_n, n)
    late = group[group["is_late"] == 1]
    recent = group[group["promised_date"] > cutoff]
    before = group[group["promised_date"] <= cutoff]

    def _share(rows: pd.DataFrame) -> float | None:
        return round(float((rows["is_late"] == 0).mean()), 4) if len(rows) else None

    return {
        "deliveries": n,
        "on_time_share": round(on_time_n / n, 4) if n else None,
        "on_time_ci_low": round(lo, 4),
        "on_time_ci_high": round(hi, 4),
        "median_days_late": float(late["delay_days"].median()) if len(late) else None,
        "p90_days_late": float(late["delay_days"].quantile(0.9)) if len(late) else None,
        "on_time_share_recent_90d": _share(recent),
        "on_time_share_before_90d": _share(before),
    }


def _scorecard(df: pd.DataFrame, group_cols: list[str], config: LabelConfig | None,
              as_of: pd.Timestamp | None) -> pd.DataFrame:
    labeled = add_labels(df, config)
    as_of = pd.Timestamp(as_of) if as_of is not None else labeled["promised_date"].max()
    cutoff = as_of - pd.Timedelta(days=TREND_WINDOW_DAYS)

    rows = []
    for key, group in labeled.groupby(group_cols, sort=False):
        key_tuple = key if isinstance(key, tuple) else (key,)
        rows.append({**dict(zip(group_cols, key_tuple)), **_rollup(group, cutoff)})

    out = pd.DataFrame(rows, columns=group_cols + [
        "deliveries", "on_time_share", "on_time_ci_low", "on_time_ci_high",
        "median_days_late", "p90_days_late",
        "on_time_share_recent_90d", "on_time_share_before_90d",
    ])
    # Worst on-time share first: an audit leads with who needs attention,
    # matching how the rest of the platform ranks (e.g. risk descending in
    # api/routers/predict.py).
    return out.sort_values("on_time_share", na_position="last").reset_index(drop=True)


def supplier_scorecard(df: pd.DataFrame, config: LabelConfig | None = None,
                       as_of: pd.Timestamp | None = None) -> pd.DataFrame:
    """One row per supplier: deliveries, on-time share with its Wilson 95%
    interval, typical (median) and worst-case (p90) days late among the late
    deliveries, and the last-90-day trend. `as_of` defaults to the latest
    `promised_date` in the data; pass it explicitly for a reproducible audit
    on a fixed date."""
    return _scorecard(df, ["supplier_id"], config, as_of)


def material_breakdown(df: pd.DataFrame, config: LabelConfig | None = None,
                       as_of: pd.Timestamp | None = None) -> pd.DataFrame:
    """Same metrics, one row per (supplier, material): a supplier can be
    reliable for one material and not another, and the scorecard alone would
    hide that."""
    return _scorecard(df, ["supplier_id", "material_type"], config, as_of)


if __name__ == "__main__":
    import sys

    from ml.ingest import load_deliveries_csv

    path = sys.argv[1] if len(sys.argv) > 1 else "sample_deliveries.csv"
    deliveries = load_deliveries_csv(path)
    print(supplier_scorecard(deliveries).to_string(index=False))
