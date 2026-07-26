"""Score a delivery (or a batch) with the trained artifact and explain WHY.

Prediction is stateless: it reads the frozen feature snapshot from the artifact
(see ROADMAP "Key design decision") instead of recomputing causal history. The
per-delivery "why" uses OCCLUSION -- replace each feature with its training median
and measure how far the risk drops; the features whose real values pushed risk up
the most are the drivers. Model-agnostic, no extra dependencies (no SHAP).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features import seasonal_severity, supplier_features_from_snapshot
from ml.train import ARTIFACT_PATH

# internal feature name -> label for the dashboard/API
FRIENDLY = {
    "supplier_late_rate": "Supplier historical late-rate",
    "mr_late_rate": "Material x route late-rate",
    "supplier_n_prior": "Supplier track-record size",
    "lead_time_days": "Lead time (days)",
    "promised_month": "Delivery month",
    "promised_dow": "Delivery weekday",
    "quantity": "Order quantity",
    "weather_severity": "Seasonal weather severity",
}
RISK_BINS = [-0.01, 0.33, 0.66, 1.01]
RISK_LABELS = ["green", "yellow", "red"]

# columns a caller must supply for each delivery
REQUIRED_FIELDS = ("supplier_id", "material_type", "route_type",
                   "quantity", "order_date", "promised_date")


def load_artifact(path=ARTIFACT_PATH) -> dict:
    import joblib
    return joblib.load(path)


def _friendly(name: str, value) -> tuple[str, str]:
    if name.startswith("mat_"):
        return f"Material = {name[4:]}", "yes"
    if name.startswith("route_"):
        return f"Route = {name[6:]}", "yes"
    label = FRIENDLY.get(name, name)
    try:
        return label, f"{float(value):.2f}"
    except (TypeError, ValueError):
        return label, str(value)


def _row_features(rec: dict, snapshot: dict) -> dict:
    order = pd.Timestamp(rec["order_date"])
    promised = pd.Timestamp(rec["promised_date"])
    sup_rate, n_prior, mr_rate = supplier_features_from_snapshot(
        snapshot, rec["material_type"], rec["route_type"], rec["supplier_id"]
    )
    month = int(promised.month)
    return {
        "supplier_late_rate": sup_rate,
        "supplier_n_prior": n_prior,
        "mr_late_rate": mr_rate,
        "lead_time_days": (promised - order).days,
        "promised_month": month,
        "promised_dow": int(promised.dayofweek),
        "quantity": float(rec["quantity"]),
        "weather_severity": seasonal_severity(month),
        f"mat_{rec['material_type']}": 1.0,
        f"route_{rec['route_type']}": 1.0,
    }


def build_matrix(records: list[dict], artifact: dict):
    """Return (X aligned to training columns, raw feature frame for the UI)."""
    raw = pd.DataFrame([_row_features(r, artifact["snapshot"]) for r in records])
    X = raw.reindex(columns=artifact["feature_columns"], fill_value=0.0).astype(float)
    return X, raw


def _drivers(model, x: np.ndarray, cols: list[str], medians: dict,
             k: int = 3, min_impact: float = 0.01) -> list[dict]:
    # Build [row, row-with-feature-neutralised x len(cols)] and score in one call.
    variants = [x]
    for c in cols:
        xj = x.copy()
        xj[cols.index(c)] = float(medians.get(c, 0.0))
        variants.append(xj)
    p = model.predict_proba(np.array(variants))[:, 1]
    ranked = sorted(zip(cols, p[0] - p[1:]), key=lambda t: t[1], reverse=True)

    drivers = []
    for name, impact in ranked[:k]:
        if impact < min_impact:
            break
        label, valstr = _friendly(name, x[cols.index(name)])
        drivers.append({"factor": label, "value": valstr, "impact": round(float(impact), 3)})
    return drivers


def score(records, artifact: dict | None = None) -> pd.DataFrame:
    """Score deliveries. `records` is a list of dicts or a DataFrame with
    REQUIRED_FIELDS. Returns risk, risk_band, key features, and top drivers."""
    if isinstance(records, pd.DataFrame):
        records = records.to_dict("records")
    artifact = artifact or load_artifact()
    model = artifact["model"]
    cols = artifact["feature_columns"]
    medians = artifact["feature_medians"]

    X, raw = build_matrix(records, artifact)
    Xv = X.to_numpy(dtype=float)
    proba = model.predict_proba(Xv)[:, 1]

    out = pd.DataFrame(
        {
            "risk": proba.round(4),
            "risk_band": pd.cut(proba, bins=RISK_BINS, labels=RISK_LABELS).astype(str),
            "supplier_late_rate": raw["supplier_late_rate"].round(3).to_numpy(),
            "supplier_n_prior": raw["supplier_n_prior"].astype(int).to_numpy(),
            "lead_time_days": raw["lead_time_days"].astype(int).to_numpy(),
        }
    )
    # Second head: expected days late. Reported for every row (it answers "if this
    # slips, by how much?"), so read it together with `risk` -- a large day count
    # on a green delivery is a low-probability, high-impact case, not a warning.
    reg = artifact.get("delay_regressor")
    if reg is not None:
        out["expected_delay_days"] = np.round(np.clip(reg.predict(Xv), 0, None), 1)
    else:
        out["expected_delay_days"] = np.nan

    out["drivers"] = [_drivers(model, Xv[i], cols, medians) for i in range(len(records))]
    return out


if __name__ == "__main__":
    if not ARTIFACT_PATH.exists():
        print("no artifact found -> training one first...")
        from ml.train import fit_and_save
        fit_and_save()

    art = load_artifact()
    samples = [
        {"supplier_id": "S07", "material_type": "ready_mix_concrete",
         "route_type": "cross_border", "quantity": 120,
         "order_date": "2025-01-05", "promised_date": "2025-01-12"},
        {"supplier_id": "NEW_9", "material_type": "bricks",         # cold-start supplier
         "route_type": "urban", "quantity": 40,
         "order_date": "2025-06-01", "promised_date": "2025-07-01"},
    ]
    res = score(samples, art)
    for rec, (_, row) in zip(samples, res.iterrows()):
        print(f"\n{rec['supplier_id']} | {rec['material_type']} | {rec['route_type']}")
        print(f"  risk={row['risk']:.2f} ({row['risk_band']})  "
              f"expected_delay={row['expected_delay_days']}d  "
              f"supplier_hist={row['supplier_late_rate']} n={row['supplier_n_prior']}")
        for d in row["drivers"]:
            print(f"    - {d['factor']} = {d['value']}  (+{d['impact']})")
    print("\nCV Avg-Precision (model vs baseline):", art["metrics"]["ap"])
