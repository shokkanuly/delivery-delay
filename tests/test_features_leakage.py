"""The leakage guard — the project's central correctness claim.

If these fail, every reported metric is suspect, because the model would be
seeing information that does not exist at prediction time.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features import build_features, build_snapshot, shrink, supplier_features_from_snapshot


def test_causal_features_ignore_the_future(synthetic_deliveries):
    """Mutating only FUTURE outcomes must not change a row's features.

    The sharpest possible statement of causality: take the earliest delivery,
    flip the labels of everything that completes after it was ordered, and its
    features must be byte-identical.
    """
    df = synthetic_deliveries.sort_values("order_date").reset_index(drop=True)
    X_before, _, _ = build_features(df)

    tampered = df.copy()
    first_order = tampered.loc[0, "order_date"]
    future = tampered["actual_date"] >= first_order
    tampered.loc[future, "is_late"] = 1 - tampered.loc[future, "is_late"]

    X_after, _, _ = build_features(tampered)
    np.testing.assert_allclose(
        X_before.iloc[0].to_numpy(dtype=float),
        X_after.iloc[0].to_numpy(dtype=float),
        err_msg="row 0 changed when only future outcomes were altered -> leakage",
    )


def test_first_delivery_has_no_prior_history(synthetic_deliveries):
    df = synthetic_deliveries.sort_values("order_date").reset_index(drop=True)
    _, _, enriched = build_features(df)
    assert enriched.loc[0, "supplier_n_prior"] == 0


def test_leaky_mode_really_is_leaky(synthetic_deliveries):
    """The deliberately-wrong path must differ, or the demo proves nothing."""
    Xc, _, _ = build_features(synthetic_deliveries, leaky=False)
    Xl, _, _ = build_features(synthetic_deliveries, leaky=True)
    assert not np.allclose(Xc["supplier_late_rate"], Xl["supplier_late_rate"])


def test_no_nans_anywhere(synthetic_deliveries):
    X, y, _ = build_features(synthetic_deliveries)
    assert not X.isna().any().any()
    assert not y.isna().any()


class TestColdStart:
    def test_unknown_supplier_falls_back_not_nan(self, synthetic_deliveries):
        snap = build_snapshot(synthetic_deliveries)
        rate, n_prior, mr = supplier_features_from_snapshot(
            snap, "ready_mix_concrete", "urban", "SUPPLIER_THAT_DOES_NOT_EXIST")
        assert n_prior == 0
        assert rate == mr, "with no history the rate must equal the material x route fallback"
        assert 0.0 <= rate <= 1.0 and not pd.isna(rate)

    def test_unknown_material_route_falls_back_to_global(self, synthetic_deliveries):
        snap = build_snapshot(synthetic_deliveries)
        rate, n_prior, mr = supplier_features_from_snapshot(
            snap, "unobtanium", "teleport", "ALSO_UNKNOWN")
        assert n_prior == 0 and 0.0 <= rate <= 1.0

    def test_known_supplier_has_history(self, synthetic_deliveries):
        snap = build_snapshot(synthetic_deliveries)
        sid = synthetic_deliveries["supplier_id"].iloc[0]
        _, n_prior, _ = supplier_features_from_snapshot(
            snap, "cement", "urban", sid)
        assert n_prior > 0


def test_shrink_endpoints():
    """No evidence -> the fallback exactly; lots of evidence -> the observation."""
    assert shrink(0, 0, 0.4, 8) == 0.4
    assert abs(shrink(10_000, 10_000, 0.0, 8) - 1.0) < 1e-3
