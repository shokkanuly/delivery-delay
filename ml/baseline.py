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


class SupplierAverageBaseline:
    """P(late) = causal, cold-start-shrunk supplier historical late-rate."""

    feature = "supplier_late_rate"

    def fit(self, X: pd.DataFrame, y=None) -> "SupplierAverageBaseline":
        return self  # nothing to fit; the rate is precomputed causally

    def predict_proba_late(self, X: pd.DataFrame) -> np.ndarray:
        return X[self.feature].to_numpy()

    def predict(self, X: pd.DataFrame, threshold: float = 0.5) -> np.ndarray:
        return (self.predict_proba_late(X) >= threshold).astype(int)
