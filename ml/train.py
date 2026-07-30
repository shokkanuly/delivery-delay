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
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score
from sklearn.model_selection import KFold, StratifiedKFold

import pathlib
from datetime import datetime, timezone

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


def make_delay_regressor(seed: int = 0):
    """Second head: how many days late, given that a delivery IS late.

    Deliberately separate from the classifier rather than a multi-output model:
    "will it slip?" and "by how much?" have different populations (the regressor
    only ever sees late rows) and different error costs, and two small models are
    easier to validate than one joint one at this data scale.
    """
    return HistGradientBoostingRegressor(
        max_depth=3, learning_rate=0.05, max_iter=400,
        l2_regularization=1.0, min_samples_leaf=15,
        early_stopping=True, validation_fraction=0.15, random_state=seed,
    )


def evaluate_delay_regressor(X: pd.DataFrame, delay_days: pd.Series,
                             is_late: pd.Series, n_splits: int = 5, seed: int = 0) -> dict:
    """CV mean-absolute-error on LATE rows, against a predict-the-mean baseline.

    MAE is in days -- directly interpretable to a site manager ("we're typically
    within N days"). The baseline is the train-fold mean delay: if the model
    can't beat that, the days estimate is not worth showing.
    """
    mask = is_late.astype(bool).to_numpy()
    Xl = X.to_numpy(dtype=float)[mask]
    yl = delay_days.to_numpy(dtype=float)[mask]
    if len(yl) < 50:
        return {"n_late_rows": int(len(yl)), "note": "too few late rows to validate"}

    model_maes, base_maes = [], []
    for tr, te in KFold(n_splits, shuffle=True, random_state=seed).split(Xl):
        m = make_delay_regressor(seed).fit(Xl[tr], yl[tr])
        model_maes.append(float(np.mean(np.abs(yl[te] - m.predict(Xl[te])))))
        base_maes.append(float(np.mean(np.abs(yl[te] - yl[tr].mean()))))

    mm, mh = _ci95(np.array(model_maes))
    bm, bh = _ci95(np.array(base_maes))
    dm, dh = _ci95(np.array(base_maes) - np.array(model_maes))   # positive = better
    return {
        "n_late_rows": int(len(yl)),
        "mae_days_model": float(round(mm, 3)), "mae_days_model_ci": float(round(mh, 3)),
        "mae_days_baseline": float(round(bm, 3)), "mae_days_baseline_ci": float(round(bh, 3)),
        "mae_improvement_days": float(round(dm, 3)),
        "mae_improvement_ci": float(round(dh, 3)),
        "beats_baseline": bool(dm - dh > 0),
    }


def evaluate_threshold_baseline(X: pd.DataFrame, y: pd.Series) -> dict:
    """Score the brief's `on_time_rate < 0.7` rule so its acceptance check is
    reported in the terms it was written in."""
    from ml.baseline import ThresholdRuleBaseline
    from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

    pred = ThresholdRuleBaseline().predict(X)
    yv = y.to_numpy()
    return {
        "rule": "predict late when supplier on-time rate < 0.7",
        "accuracy": float(round(accuracy_score(yv, pred), 4)),
        "precision": float(round(precision_score(yv, pred, zero_division=0), 4)),
        "recall": float(round(recall_score(yv, pred, zero_division=0), 4)),
        "f1": float(round(f1_score(yv, pred, zero_division=0), 4)),
    }


def make_status_model(seed: int = 0):
    """3-class head (early / on_time / late) — needs its own configuration.

    Two departures from the binary classifier, both measured rather than assumed:
      * `class_weight="balanced"` — `early` is ~2% of rows, so unweighted
        multiclass log-loss simply learns to never predict it.
      * patient early stopping — multiclass validation loss plateaus early and
        then improves; the binary settings stopped after ~11 iterations and the
        model collapsed onto the majority class (late F1 0.04). With these,
        late F1 ~0.41 and `early` is predicted at all.
    """
    return HistGradientBoostingClassifier(
        max_depth=3, learning_rate=0.05, max_iter=300,
        l2_regularization=1.0, min_samples_leaf=20,
        class_weight="balanced",
        early_stopping=True, validation_fraction=0.2, n_iter_no_change=40,
        random_state=seed,
    )


def evaluate_status_classifier(X: pd.DataFrame, status: pd.Series,
                               n_splits: int = 5, seed: int = 0) -> dict:
    """CV the 3-class head (early / on_time / late) the brief asked for.

    Reported PER CLASS on purpose: `early` is a small minority, and a flattering
    macro average would hide that the model barely predicts it at all.
    """
    from sklearn.metrics import classification_report

    yv = status.to_numpy()
    Xv = X.to_numpy(dtype=float)
    counts = pd.Series(yv).value_counts().to_dict()
    if min(counts.values()) < n_splits:
        return {"note": "a class has too few rows to cross-validate",
                "class_counts": counts}

    preds = np.empty(len(yv), dtype=object)
    for tr, te in StratifiedKFold(n_splits, shuffle=True, random_state=seed).split(Xv, yv):
        preds[te] = make_status_model(seed).fit(Xv[tr], yv[tr]).predict(Xv[te])

    rep = classification_report(yv, preds.astype(str), output_dict=True, zero_division=0)
    return {
        "class_counts": {k: int(v) for k, v in counts.items()},
        "accuracy": float(round(rep["accuracy"], 4)),
        "macro_f1": float(round(rep["macro avg"]["f1-score"], 4)),
        "per_class_f1": {c: float(round(rep[c]["f1-score"], 4))
                         for c in counts if c in rep},
    }


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

    # Second head: expected delay in days, fitted on late rows only.
    late_mask = y.astype(bool).to_numpy()
    delay_metrics = evaluate_delay_regressor(X, df["delay_days"], y, seed=seed)
    delay_regressor = None
    if late_mask.sum() >= 50:
        delay_regressor = make_delay_regressor(seed).fit(
            X.to_numpy(dtype=float)[late_mask],
            df["delay_days"].to_numpy(dtype=float)[late_mask],
        )

    # Third head: the brief's 3-class status (early / on_time / late).
    status = add_labels(df, LabelConfig(mode="three_class"))["delivery_status"]
    status_metrics = evaluate_status_classifier(X, status, seed=seed)
    status_model = None
    if "per_class_f1" in status_metrics:
        status_model = make_status_model(seed).fit(X.to_numpy(dtype=float), status.to_numpy())

    trained_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    artifact = {
        "model": model,
        "delay_regressor": delay_regressor,
        "status_model": status_model,
        "status_classes": (list(status_model.classes_) if status_model is not None else []),
        "feature_columns": list(X.columns),
        "feature_medians": {k: float(v) for k, v in X.median().to_dict().items()},
        "snapshot": build_snapshot(df, k_shrink=k_shrink, prior_late_rate=prior_late_rate),
        "metrics": metrics_summary(folds),
        "delay_metrics": delay_metrics,
        "status_metrics": status_metrics,
        "threshold_baseline": evaluate_threshold_baseline(X, y),
        "trained_rows": int(len(df)),
        "trained_at": trained_at,
        # Stamped onto every logged prediction so realized accuracy can always be
        # traced back to the exact model that produced it.
        "model_version": f"{trained_at[:16]}-n{len(df)}-f{len(X.columns)}",
    }
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, path)
    return artifact, folds


if __name__ == "__main__":
    import sys

    csv = next((a for a in sys.argv[1:] if not a.startswith("-")), None)
    artifact, folds = fit_and_save(csv_path=csv)
    print(f"saved artifact -> {ARTIFACT_PATH}  ({artifact['trained_rows']} rows, "
          f"version {artifact['model_version']})\n")
    print(summarize(folds))
    dm = artifact["delay_metrics"]
    if "mae_days_model" in dm:
        verdict = "beats baseline" if dm["beats_baseline"] else "no clear win"
        print(f"\n  Expected delay (days, late rows only, n={dm['n_late_rows']})")
        print(f"  {'MAE days':<24} baseline {dm['mae_days_baseline']:.2f} "
              f"+/-{dm['mae_days_baseline_ci']:.2f}   "
              f"model {dm['mae_days_model']:.2f} +/-{dm['mae_days_model_ci']:.2f}   "
              f"better by {dm['mae_improvement_days']:+.2f} "
              f"+/-{dm['mae_improvement_ci']:.2f}  [{verdict}]")
    else:
        print(f"\n  Expected delay head skipped: {dm.get('note')}")
