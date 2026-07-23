"""End-to-end demo tying Problems 1-4 together.

    python run.py

Prints: the label definition (P4), a leakage check causal-vs-leaky (P2), a
cold-start report with example fallback predictions (P3), and the cross-validated
model-vs-baseline comparison with confidence intervals (P1).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ml.data_sim import generate_deliveries
from ml.features import build_features
from ml.labeling import DEFAULT_GRACE_DAYS, LabelConfig, add_labels
from ml.train import cross_validate, summarize

pd.set_option("display.width", 120)


def _rule(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def main() -> None:
    df = generate_deliveries(n=1200, seed=7)

    # ---- Problem 4: label definition --------------------------------------
    _rule("PROBLEM 4  |  Label definition (per-material grace window)")
    cfg = LabelConfig(mode="binary")
    df = add_labels(df, cfg)
    print(f"grace days by material: {DEFAULT_GRACE_DAYS}")
    print(f"overall late rate: {df['is_late'].mean():.1%}  (n={len(df)})")
    print("late rate by material:")
    print(df.groupby("material_type")["is_late"].mean()
            .sort_values().round(3).to_string())

    # ---- Problem 2: leakage check -----------------------------------------
    _rule("PROBLEM 2  |  Leakage check: causal features vs. leaky features")
    Xc, yc, enr = build_features(df, leaky=False)
    Xl, yl, _ = build_features(df, leaky=True)
    causal = cross_validate(Xc, yc)
    leaky = cross_validate(Xl, yl)
    print(f"  causal  features -> CV Avg Precision {causal['ap_model'].mean():.3f}")
    print(f"  LEAKY   features -> CV Avg Precision {leaky['ap_model'].mean():.3f}"
          "   <- inflated mirage; do NOT ship")
    print("  The gap is the fantasy accuracy you'd have demoed with naive"
          " group-mean features.")

    # ---- Problem 3: cold start --------------------------------------------
    _rule("PROBLEM 3  |  Cold-start suppliers still get a sensible prediction")
    cold = enr[enr["supplier_n_prior"] == 0].copy()
    cold["mr_late_rate"] = Xc.loc[cold.index, "mr_late_rate"]
    print(f"cold-start rows (zero prior supplier history): {len(cold)} "
          f"({len(cold)/len(enr):.1%})")
    print("examples -> a NEW supplier joining a running operation: with no"
          " supplier history the shrinkage formula collapses supplier_late_rate"
          " onto the (populated) material x route rate, never NaN:")
    print(cold.tail(4)[["supplier_id", "material_type", "route_type",
                        "mr_late_rate", "supplier_late_rate"]]
          .round(3).to_string(index=False))

    # ---- Problem 1: baseline + CV with confidence intervals ---------------
    _rule("PROBLEM 1  |  Model vs. supplier-average baseline (5-fold CV, 95% CI)")
    print(summarize(causal))
    print("\nRead the 'lift' column: positive with a CI clear of 0 = the ML model"
          " adds credible value beyond supplier history.")


if __name__ == "__main__":
    main()
