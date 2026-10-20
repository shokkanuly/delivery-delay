"""An isolated chronological audit; never loads or writes a serving artifact."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from ml.baseline import SupplierAverageBaseline
from ml.features import build_features, build_snapshot
from ml.labeling import add_labels
from ml.predict import RISK_BINS, RISK_LABELS, build_matrix
from ml.train import make_model


def chronological_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """First 70% of orders vs the rest, keeping equal order dates together.

    Training outcomes must already be resolved strictly before the first held-
    out order. Otherwise even a frozen snapshot would leak future completions.
    Invalid chronology is excluded from backtesting, not from the scorecard.
    """
    valid = (df.actual_date >= df.order_date) & (df.promised_date >= df.order_date)
    history = df.loc[valid].sort_values("order_date", kind="stable").reset_index(drop=True)
    info = {"excluded_chronology": int((~valid).sum()), "purged_train_rows": 0,
            "cutoff": None, "train_order_max": None, "train_actual_max": None,
            "test_order_min": None}
    if len(history) < 2:
        return history, history.iloc[:0], info
    cutoff = history.iloc[min(int(len(history) * 0.7), len(history) - 1)].order_date
    candidates = history[history.order_date < cutoff]
    train = candidates[candidates.actual_date < cutoff].copy()
    test = history[history.order_date >= cutoff].copy()
    info.update(cutoff=cutoff.isoformat(), purged_train_rows=len(candidates) - len(train),
                train_order_max=train.order_date.max().isoformat() if len(train) else None,
                train_actual_max=train.actual_date.max().isoformat() if len(train) else None,
                test_order_min=test.order_date.min().isoformat())
    return train, test, info


def band_outcomes(y: np.ndarray, probabilities: np.ndarray) -> dict:
    """Realized late rates using the same band boundaries as online scoring."""
    bands = pd.cut(probabilities, bins=RISK_BINS, labels=RISK_LABELS)
    return {band: {"deliveries": int((bands == band).sum()),
                   "late_rate": float(y[bands == band].mean()) if (bands == band).any() else None}
            for band in RISK_LABELS}


def history_backtest(df: pd.DataFrame) -> dict:
    """Fit the existing classifier in memory on past orders, then freeze it.

    Held-out labels never enter features, training, early stopping or snapshot.
    Metrics describe one historical split, not a confidence claim or live proof.
    Only a model beating the supplier baseline releases a risk-band breakdown.
    """
    labeled = add_labels(df) if len(df) else df.copy()
    train, test, info = chronological_split(labeled)
    report = {**info, "status": "insufficient_data", "reason": None,
              "train_rows": len(train), "test_rows": len(test),
              "model_average_precision": None, "baseline_average_precision": None,
              "lift": None, "beats_baseline": None, "risk_bands": {}}
    if len(train) < 50 or len(test) < 20:
        report["reason"] = "Для проверки нужны минимум 50 завершённых обучающих и 20 проверочных поставок после временного разделения."
        return report
    if train.is_late.nunique() < 2 or train.is_late.value_counts().min() < 5:
        report["reason"] = "В обучающей истории нужны хотя бы 5 своевременных и 5 опоздавших поставок."
        return report
    if test.is_late.nunique() < 2 or test.is_late.value_counts().min() < 2:
        report["reason"] = "В проверочном периоде нужны хотя бы 2 своевременные и 2 опоздавшие поставки."
        return report

    X, y, _ = build_features(train)
    model = make_model(seed=0).fit(X.to_numpy(dtype=float), y.to_numpy())
    # A temporary in-memory artifact, aligned only to the training vocabulary.
    temporary = {"snapshot": build_snapshot(train), "feature_columns": list(X.columns)}
    held_out, _ = build_matrix(test.to_dict("records"), temporary)
    probabilities = model.predict_proba(held_out.to_numpy(dtype=float))[:, 1]
    baseline = SupplierAverageBaseline().predict_proba_late(held_out)
    actual = test.is_late.to_numpy(dtype=int)
    model_ap = float(average_precision_score(actual, probabilities))
    baseline_ap = float(average_precision_score(actual, baseline))
    beats = model_ap > baseline_ap + 1e-12
    report.update(status="evaluated", model_average_precision=model_ap,
                  baseline_average_precision=baseline_ap, lift=model_ap - baseline_ap,
                  beats_baseline=beats,
                  risk_bands=band_outcomes(actual, probabilities) if beats else {})
    return report
