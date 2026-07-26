"""Honest end-to-end evidence demo: train on the past, predict the future.

    python3 -m scripts.evidence_loop

Why this exists. Replaying predictions over rows the model was trained on gives
a flattering number that means nothing. This script does the real thing:

    1. sort every delivery by order_date
    2. train on the OLDEST 80%   (the past)
    3. serve predictions on the NEWEST 20% (the future — never seen in training)
    4. feed back what actually happened
    5. score served predictions against reality

Step 2->3 is also a time-ordered holdout, so it stress-tests drift in a way that
random k-fold cannot: the test rows all happen after the training rows, exactly
like production.

The headline number for a non-technical audience is the CALIBRATION table: how
often each risk band actually ran late. "Red deliveries slipped 3x as often as
green" needs no ML background to believe.
"""
from __future__ import annotations

import pathlib
import tempfile

import pandas as pd

from ml.ingest import load_deliveries_csv
from ml.labeling import LabelConfig, add_labels
from ml.predict import load_artifact, score
from ml.train import fit_and_save

SOURCE = pathlib.Path("data/synthetic/delay_prediction.csv")
TRAIN_FRACTION = 0.8
LATE_THRESHOLD = 0.5
GRACE_DAYS = 1


def main() -> None:
    df = load_deliveries_csv(SOURCE, require_actual=True).sort_values("order_date")
    cut = int(len(df) * TRAIN_FRACTION)
    past, future = df.iloc[:cut].copy(), df.iloc[cut:].copy()
    print(f"train (past)   : {len(past):5d} rows  "
          f"{past['order_date'].min().date()} -> {past['order_date'].max().date()}")
    print(f"serve (future) : {len(future):5d} rows  "
          f"{future['order_date'].min().date()} -> {future['order_date'].max().date()}")

    with tempfile.TemporaryDirectory() as tmp:
        train_csv = pathlib.Path(tmp) / "past.csv"
        past.to_csv(train_csv, index=False)
        artifact_path = pathlib.Path(tmp) / "past_model.joblib"
        fit_and_save(path=artifact_path, csv_path=str(train_csv))
        artifact = load_artifact(artifact_path)

        scored = score(
            future[["supplier_id", "material_type", "route_type", "quantity",
                    "order_date", "promised_date"]].to_dict("records"),
            artifact,
        )

    truth = add_labels(future, LabelConfig())["is_late"].to_numpy()
    pred_late = (scored["risk"] >= LATE_THRESHOLD).astype(int).to_numpy()

    tp = int(((pred_late == 1) & (truth == 1)).sum())
    fp = int(((pred_late == 1) & (truth == 0)).sum())
    fn = int(((pred_late == 0) & (truth == 1)).sum())
    tn = int(((pred_late == 0) & (truth == 0)).sum())
    n = len(truth)

    print(f"\n=== REALIZED PERFORMANCE ON UNSEEN FUTURE DELIVERIES (n={n}) ===")
    print(f"  accuracy   : {(tp + tn) / n:.3f}")
    if tp + fp:
        print(f"  precision  : {tp / (tp + fp):.3f}   (of those flagged late, how many were)")
    if tp + fn:
        print(f"  recall     : {tp / (tp + fn):.3f}   (of those that ran late, how many we caught)")
    print(f"  confusion  : tp={tp} fp={fp} fn={fn} tn={tn}")
    print(f"  base rate  : {truth.mean():.1%} of these deliveries actually ran late")

    print("\n=== CALIBRATION — the number to show a non-technical audience ===")
    out = pd.DataFrame({"band": scored["risk_band"], "late": truth})
    for band in ("green", "yellow", "red"):
        sel = out[out["band"] == band]
        if len(sel):
            print(f"  {band:6s} n={len(sel):4d}   actually ran late: {sel['late'].mean():6.1%}")
    print("\n  A monotonic green < yellow < red spread is the claim that matters:")
    print("  the flags rank real risk, so acting on red first is provably worthwhile.")


if __name__ == "__main__":
    main()
