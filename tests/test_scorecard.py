"""Stage 2 (docs/plans/mvp-reshape.md): the supplier scorecard.

Covers the Done when of Stage 2: known-answer tests (7 of 10 on time -> 0.70,
Wilson interval checked against an independently hand-derived reference
value) pass; tests/test_layering.py still passes (checked separately, but
every fixture here stays import-clean of fastapi/streamlit/requests/api on
purpose).
"""
from __future__ import annotations

import pandas as pd
import pytest

from ml.scorecard import material_breakdown, supplier_scorecard, wilson_interval


def _delivery(supplier, material, promised, delay_days, order=None):
    promised = pd.Timestamp(promised)
    return {
        "supplier_id": supplier, "material_type": material,
        "order_date": pd.Timestamp(order) if order else promised - pd.Timedelta(days=10),
        "promised_date": promised,
        "actual_date": promised + pd.Timedelta(days=delay_days),
    }


class TestWilsonInterval:
    def test_known_answer_7_of_10(self):
        """7/10 -> point estimate 0.70; interval against an independently
        re-derived value of the same published formula (not the module's own
        code), so this doesn't just check the function against itself."""
        lo, hi = wilson_interval(7, 10)
        assert 7 / 10 == pytest.approx(0.70)
        assert lo == pytest.approx(0.396773, abs=1e-6)
        assert hi == pytest.approx(0.892211, abs=1e-6)

    def test_zero_trials_is_maximum_uncertainty(self):
        assert wilson_interval(0, 0) == (0.0, 1.0)

    def test_never_collapses_to_a_point_at_the_extremes(self):
        """The whole reason to use Wilson over a normal approximation at
        small n: 10/10 and 0/10 must still have real width."""
        lo, hi = wilson_interval(10, 10)
        assert lo > 0.0 and hi == 1.0
        lo, hi = wilson_interval(0, 10)
        assert lo == 0.0 and hi < 1.0

    def test_stays_inside_zero_one(self):
        for successes, n in [(0, 1), (1, 1), (50, 50), (1, 1000)]:
            lo, hi = wilson_interval(successes, n)
            assert 0.0 <= lo <= hi <= 1.0


class TestSupplierScorecard:
    def test_known_answer_seven_of_ten_on_time(self):
        """rebar grace is 2 days (ml.labeling.DEFAULT_GRACE_DAYS): delays of
        0,1,2,-1,-2,0,1 are on time; 3,5,10 are late. 7 on time of 10 ->
        0.70, matching the Wilson known-answer above exactly."""
        rows = [_delivery("S1", "rebar", "2026-01-10", d)
               for d in (0, 1, 2, -1, -2, 0, 1, 3, 5, 10)]
        sc = supplier_scorecard(pd.DataFrame(rows))

        assert len(sc) == 1
        row = sc.iloc[0]
        assert row["supplier_id"] == "S1"
        assert row["deliveries"] == 10
        assert row["on_time_share"] == pytest.approx(0.70)
        assert row["on_time_ci_low"] == pytest.approx(0.396773, abs=1e-4)
        assert row["on_time_ci_high"] == pytest.approx(0.892211, abs=1e-4)
        # late delays are 3, 5, 10 -> median 5, p90 (pandas linear interp) 9.0
        assert row["median_days_late"] == pytest.approx(5.0)
        assert row["p90_days_late"] == pytest.approx(9.0)

    def test_no_late_deliveries_gives_none_not_zero(self):
        """A supplier who is never late has an UNDEFINED typical lateness,
        not a lateness of zero days -- those mean different things to a site
        manager reading the scorecard."""
        rows = [_delivery("S3", "bricks", "2026-01-10", 0) for _ in range(4)]
        sc = supplier_scorecard(pd.DataFrame(rows))
        row = sc.iloc[0]
        assert row["median_days_late"] is None
        assert row["p90_days_late"] is None

    def test_trend_splits_on_the_90_day_window(self):
        """5 old on-time deliveries, then 5 recent late-by-5-days deliveries
        (cement grace is 1 day), as_of pinned to the recent batch's date so
        the 90-day cutoff falls cleanly between the two groups."""
        old, recent = pd.Timestamp("2026-01-10"), pd.Timestamp("2026-05-10")  # 120 days apart
        rows = ([_delivery("S2", "cement", old, 0) for _ in range(5)]
               + [_delivery("S2", "cement", recent, 5) for _ in range(5)])
        sc = supplier_scorecard(pd.DataFrame(rows), as_of=recent)
        row = sc.iloc[0]
        assert row["on_time_share"] == pytest.approx(0.5)
        assert row["on_time_share_recent_90d"] == pytest.approx(0.0)
        assert row["on_time_share_before_90d"] == pytest.approx(1.0)

    def test_trend_bucket_with_no_rows_is_none(self):
        rows = [_delivery("S1", "rebar", "2026-01-10", 0)]
        sc = supplier_scorecard(pd.DataFrame(rows))
        assert sc.iloc[0]["on_time_share_before_90d"] is None

    def test_sorted_worst_first(self):
        """An audit leads with who needs attention: lowest on-time share
        first, matching the rest of the platform's risk-descending order."""
        rows = ([_delivery("GOOD", "rebar", "2026-01-10", 0) for _ in range(5)]
               + [_delivery("BAD", "rebar", "2026-01-10", 10) for _ in range(5)])
        sc = supplier_scorecard(pd.DataFrame(rows))
        assert list(sc["supplier_id"]) == ["BAD", "GOOD"]

    def test_multiple_suppliers_get_independent_rows(self):
        rows = ([_delivery("S1", "rebar", "2026-01-10", 0) for _ in range(3)]
               + [_delivery("S2", "rebar", "2026-01-10", 10) for _ in range(2)])
        sc = supplier_scorecard(pd.DataFrame(rows))
        assert set(sc["supplier_id"]) == {"S1", "S2"}
        assert sc.set_index("supplier_id").loc["S1", "deliveries"] == 3
        assert sc.set_index("supplier_id").loc["S2", "deliveries"] == 2


class TestMaterialBreakdown:
    def test_one_row_per_supplier_material_pair(self):
        """Same supplier, two materials, two different reliability records --
        the scorecard alone would average these together and hide it."""
        rows = ([_delivery("S1", "rebar", "2026-01-10", 0) for _ in range(5)]      # always on time
               + [_delivery("S1", "cement", "2026-01-10", 10) for _ in range(5)])  # always late
        mb = material_breakdown(pd.DataFrame(rows))
        assert len(mb) == 2
        by_material = mb.set_index("material_type")
        assert by_material.loc["rebar", "on_time_share"] == pytest.approx(1.0)
        assert by_material.loc["cement", "on_time_share"] == pytest.approx(0.0)

    def test_matches_supplier_rollup_when_one_material(self):
        rows = [_delivery("S1", "rebar", "2026-01-10", d) for d in (0, 1, 2, 3, 5, 10)]
        df = pd.DataFrame(rows)
        sc_share = supplier_scorecard(df).iloc[0]["on_time_share"]
        mb_share = material_breakdown(df).iloc[0]["on_time_share"]
        assert sc_share == mb_share
