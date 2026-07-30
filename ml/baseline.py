"""Problem 1 -- the baseline the ML model must beat, always shown in the demo.

The classic rule of thumb is "trust the supplier's historical average." Here that
rule is already computed for us, causally and with cold-start fallback, as the
`supplier_late_rate` column from features.py. So the baseline is parameter-free:
it simply predicts that causal historical late-rate.

Reporting the ML model next to this number is what makes the model's lift
*credible* to non-technical judges -- if the gradient booster can't clearly beat
"just look at the supplier's track record," that is itself the finding.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


class ThresholdRuleBaseline:
    """The brief's stated rule: flag late when the supplier's on-time rate < 0.7.

    Implemented against the CAUSAL supplier rate (1 - supplier_late_rate) rather
    than the shipped `supplier_on_time_rate_hist` column, which is a single
    constant per supplier correlating 0.975 with that supplier's full-period
    outcome -- i.e. future information. Same rule, honest inputs.

    Reported alongside the smoother SupplierAverageBaseline because it is the
    acceptance check the brief actually specified.
    """

    def __init__(self, on_time_threshold: float = 0.7):
        self.on_time_threshold = on_time_threshold

    def fit(self, X=None, y=None) -> "ThresholdRuleBaseline":
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        on_time_rate = 1.0 - X["supplier_late_rate"].to_numpy()
        return (on_time_rate < self.on_time_threshold).astype(int)

    def predict_proba_late(self, X: pd.DataFrame) -> np.ndarray:
        """A hard rule has no scores; expose the decision as 0/1 so it can be
        scored with the same metrics as everything else."""
        return self.predict(X).astype(float)


class SupplierAverageBaseline:
    """P(late) = causal, cold-start-shrunk supplier historical late-rate."""

    feature = "supplier_late_rate"

    def fit(self, X: pd.DataFrame, y=None) -> "SupplierAverageBaseline":
        return self  # nothing to fit; the rate is precomputed causally

    def predict_proba_late(self, X: pd.DataFrame) -> np.ndarray:
        return X[self.feature].to_numpy()

    def predict(self, X: pd.DataFrame, threshold: float = 0.5) -> np.ndarray:
        return (self.predict_proba_late(X) >= threshold).astype(int)
