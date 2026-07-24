"""Problem 1 -- honest evaluation on small data: k-fold CV, confidence
intervals, and a paired comparison against the supplier-average baseline.

We report:
  * Average Precision (PR-AUC) FIRST -- it is the right metric for catching a
    minority "late" class; ROC-AUC alongside for familiarity.
  * mean +/- a 95% CI across folds (Student-t, k-1 dof) so nobody over-reads a
    single lucky split.
  * the PAIRED per-fold lift (model - baseline) with its own CI -- the paired
    delta cancels fold-to-fold difficulty and is the credible "does ML help?"
    number.

The model is deliberately small and regularized (shallow trees, L2, early
stopping, few features, no raw high-cardinality supplier id) because the enemy on
a few thousand rows is overfitting, not underfitting.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold

import pathlib

import joblib

from ml.baseline import SupplierAverageBaseline
from ml.data_sim import generate_deliveries
from ml.features import build_features, build_snapshot
from ml.labeling import LabelConfig, add_labels

ARTIFACT_PATH = pathlib.Path(__file__).resolve().parent / "artifacts" / "model.joblib"


def make_model(seed: int = 0):
    """Default classifier. Swap for LightGBM by returning:
        import lightgbm as lgb
        return lgb.LGBMClassifier(n_estimators=500, learning_rate=0.05,
                                  num_leaves=15, reg_lambda=1.0,
                                  min_child_samples=20, random_state=seed)
    """
    return HistGradientBoostingClassifier(
        max_depth=3,
        learning_rate=0.05,
        max_iter=500,
        l2_regularization=1.0,
        min_samples_leaf=20,
        early_stopping=True,
        validation_fraction=0.15,
        random_state=seed,
    )


def _ci95(x: np.ndarray):
    """Mean and 95% CI half-width (t-based, small-sample honest)."""
    x = np.asarray(x, dtype=float)
    m = x.mean()
    if len(x) < 2:
        return m, 0.0
    se = x.std(ddof=1) / np.sqrt(len(x))
    return m, stats.t.ppf(0.975, len(x) - 1) * se


def cross_validate(X: pd.DataFrame, y: pd.Series, n_splits: int = 5, seed: int = 0):
    """Return a per-fold DataFrame of baseline vs. model metrics."""
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    Xv = X.to_numpy(dtype=float)
    yv = y.to_numpy()
    base = SupplierAverageBaseline()

    rows = []
    for fold, (tr, te) in enumerate(skf.split(Xv, yv)):
        model = make_model(seed).fit(Xv[tr], yv[tr])
        p_model = model.predict_proba(Xv[te])[:, 1]
        p_base = base.predict_proba_late(X.iloc[te])  # no fitting needed

        rows.append(
            {
                "fold": fold,
                "ap_base": average_precision_score(yv[te], p_base),
                "ap_model": average_precision_score(yv[te], p_model),
                "auc_base": roc_auc_score(yv[te], p_base),
                "auc_model": roc_auc_score(yv[te], p_model),
                "f1_base": f1_score(yv[te], (p_base >= 0.5).astype(int)),
                "f1_model": f1_score(yv[te], (p_model >= 0.5).astype(int)),
            }
        )
    return pd.DataFrame(rows)


def summarize(folds: pd.DataFrame) -> str:
    """Human-readable report with CIs and the paired lift."""
    lines = []
    for metric, label in [("ap", "Avg Precision (PR-AUC)"),
                          ("auc", "ROC-AUC"),
                          ("f1", "F1 @0.5")]:
        bm, bh = _ci95(folds[f"{metric}_base"])
        mm, mh = _ci95(folds[f"{metric}_model"])
        dm, dh = _ci95(folds[f"{metric}_model"] - folds[f"{metric}_base"])
        verdict = "model wins" if dm - dh > 0 else (
            "no clear win" if dm + dh > 0 else "baseline wins")
        lines.append(
            f"  {label:<24} baseline {bm:.3f} +/-{bh:.3f}   "
            f"model {mm:.3f} +/-{mh:.3f}   "
            f"lift {dm:+.3f} +/-{dh:.3f}  [{verdict}]"
        )
    return "\n".join(lines)


def metrics_summary(folds: pd.DataFrame) -> dict:
    """Compact numeric CV summary (means + 95% CIs + paired lift) for API/UI."""
    out = {}
    for m in ("ap", "auc", "f1"):
        bm, bh = _ci95(folds[f"{m}_base"])
        mm, mh = _ci95(folds[f"{m}_model"])
        dm, dh = _ci95(folds[f"{m}_model"] - folds[f"{m}_base"])
        out[m] = {
            "baseline": float(round(bm, 3)), "baseline_ci": float(round(bh, 3)),
            "model": float(round(mm, 3)), "model_ci": float(round(mh, 3)),
            "lift": float(round(dm, 3)), "lift_ci": float(round(dh, 3)),
        }
    return out


def load_training_frame(n: int = 1200, seed: int = 7,
                        csv_path: str | None = None) -> pd.DataFrame:
    """Synthetic by default; pass csv_path to train on a real deliveries CSV
    (validated via ml.ingest). Swap either for a SELECT from the deliveries table."""
    if csv_path:
        from ml.ingest import load_deliveries_csv
        df = load_deliveries_csv(csv_path, require_actual=True)
    else:
        df = generate_deliveries(n=n, seed=seed)
    return add_labels(df, LabelConfig())


def fit_and_save(path=ARTIFACT_PATH, n: int = 1200, seed: int = 7,
                 k_shrink: float = 8.0, prior_late_rate: float = 0.35,
                 csv_path: str | None = None):
    """Train on all data, snapshot the causal rate tables, and persist everything
    /predict needs into one joblib artifact. Returns (artifact, cv_folds)."""
    df = load_training_frame(n=n, seed=seed, csv_path=csv_path)
    X, y, _ = build_features(df, k_shrink=k_shrink, prior_late_rate=prior_late_rate)
    folds = cross_validate(X, y)                       # honest held-out metrics
    model = make_model(seed).fit(X.to_numpy(dtype=float), y.to_numpy())
    artifact = {
        "model": model,
        "feature_columns": list(X.columns),
        "feature_medians": {k: float(v) for k, v in X.median().to_dict().items()},
        "snapshot": build_snapshot(df, k_shrink=k_shrink, prior_late_rate=prior_late_rate),
        "metrics": metrics_summary(folds),
        "trained_rows": int(len(df)),
    }
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, path)
    return artifact, folds


if __name__ == "__main__":
    artifact, folds = fit_and_save()
    print(f"saved artifact -> {ARTIFACT_PATH}  ({artifact['trained_rows']} rows)\n")
    print(summarize(folds))
