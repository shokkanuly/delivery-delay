"""Unsupervised sequencing anomalies (Isolation Forest).

The rules in rules.py catch what we can state explicitly ("arrived before the
phase began"). This layer catches patterns nobody wrote a rule for: a delivery
that is technically *allowed* for its phase but sits far from how that
material/phase combination normally behaves -- e.g. arriving at the very end of
its window in unusually large quantities, which historically causes storage
problems.

Deliberately SECONDARY and reported separately from the rules:
  * it is unsupervised, so it has no precision/recall to quote;
  * it produces suspicions, not violations, and must never dilute the rules'
    perfect recall on `premature_delivery`.

Meaningful only once enough real history has accumulated -- with little data it
mostly rediscovers the rules. `min_rows` enforces that rather than silently
returning noise.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

MIN_ROWS = 100
CONTAMINATION = 0.05          # expected share of anomalies; tune on real data


@dataclass
class AnomalyResult:
    rows: list[dict]
    fitted: bool
    note: str = ""


def _design_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Timing/size features describing HOW a delivery sits within its phase."""
    d = df.copy()
    for col in ("delivery_date", "phase_start_date", "phase_end_date"):
        d[col] = pd.to_datetime(d[col], errors="coerce")

    span = (d["phase_end_date"] - d["phase_start_date"]).dt.days.replace(0, np.nan)
    offset = (d["delivery_date"] - d["phase_start_date"]).dt.days

    X = pd.DataFrame(index=d.index)
    X["days_into_phase"] = offset.fillna(0)
    X["phase_span_days"] = span.fillna(span.median() if span.notna().any() else 1)
    # where in the window it lands: 0 = at the start, 1 = at the very end
    X["position_in_phase"] = (offset / span).replace([np.inf, -np.inf], np.nan).fillna(0.5)
    if "quantity" in d.columns:
        X["quantity"] = pd.to_numeric(d["quantity"], errors="coerce").fillna(0)
    X = pd.concat([X, pd.get_dummies(d["required_phase"], prefix="phase", dtype=float)],
                  axis=1)
    return X


def detect_anomalies(deliveries: pd.DataFrame, contamination: float = CONTAMINATION,
                     min_rows: int = MIN_ROWS, seed: int = 0) -> AnomalyResult:
    """Flag deliveries that sit far from normal timing for their phase."""
    if len(deliveries) < min_rows:
        return AnomalyResult(
            rows=[], fitted=False,
            note=(f"needs at least {min_rows} deliveries to be meaningful "
                  f"(got {len(deliveries)}); rules-only until real history accumulates"))

    from sklearn.ensemble import IsolationForest

    X = _design_matrix(deliveries)
    model = IsolationForest(n_estimators=200, contamination=contamination,
                            random_state=seed)
    flags = model.fit_predict(X.to_numpy(dtype=float))
    scores = model.score_samples(X.to_numpy(dtype=float))

    rows = []
    for (_, src), flag, s in zip(deliveries.iterrows(), flags, scores):
        row = src.to_dict()
        row["anomaly"] = bool(flag == -1)
        row["anomaly_score"] = float(round(-s, 4))     # higher = more unusual
        if row["anomaly"]:
            pos = float(X.loc[src.name, "position_in_phase"])
            where = ("before its phase window" if pos < 0
                     else "late in its phase window" if pos > 0.85
                     else "unusually within its phase window")
            row["anomaly_reason"] = (
                f"unusual timing/size for {src['material_type']} in "
                f"'{src['required_phase']}' — arrives {where}")
        rows.append(row)
    return AnomalyResult(rows=rows, fitted=True)
