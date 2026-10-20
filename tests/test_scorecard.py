"""Known-answer checks for descriptive supplier reliability, not model accuracy."""
from pathlib import Path

import pandas as pd
import pytest

from ml.ingest import load_export
from ml.scorecard import material_breakdown, supplier_scorecard, wilson_interval


def history():
    # 5 old arrivals: 2 on time, 3 late (delays 1, 3, 10); 5 recent, all on time.
    promised = pd.to_datetime(["2026-01-01"] * 5 + ["2026-10-01"] * 5)
    return pd.DataFrame({
        "supplier_id": ["A"] * 10, "material_type": ["ready_mix_concrete"] * 10,
        "promised_date": promised,
        "actual_date": promised + pd.to_timedelta([0, 0, 1, 3, 10, 0, 0, 0, 0, 0], unit="D"),
    })


def test_wilson_seven_of_ten():
    low, high = wilson_interval(7, 10)
    assert low == pytest.approx(0.39677814746114537)
    assert high == pytest.approx(0.8922087325936989)


def test_wilson_empty_and_extremes():
    assert wilson_interval(0, 0) == (None, None)
    assert wilson_interval(0, 10)[1] == pytest.approx(0.2775327998628892)
    assert wilson_interval(10, 10)[0] == pytest.approx(0.7224672001371107)
    for args in ((-1, 10), (11, 10), (0, -1), (1.5, 10)):
        with pytest.raises(ValueError):
            wilson_interval(*args)


def test_counts_interval_quantiles_and_trend():
    row = supplier_scorecard(history()).iloc[0]
    assert (row.supplier_id, row.deliveries, row.on_time, row.late) == ("A", 10, 7, 3)
    assert row.on_time_share == 0.7
    assert row.on_time_ci_low == pytest.approx(0.39677814746114537)
    assert row.on_time_ci_high == pytest.approx(0.8922087325936989)
    assert row.median_late_days == 3
    assert row.p90_late_days == pytest.approx(8.6)
    assert (row.recent_deliveries, row.previous_deliveries) == (5, 5)
    assert (row.recent_on_time_share, row.previous_on_time_share) == (1, 0.4)
    assert row.trend_pp == pytest.approx(60)


def test_material_grace_and_stale_labels():
    frame = history().iloc[:3].copy()
    frame["material_type"] = ["cement", "rebar", "unknown"]
    frame["actual_date"] = frame.promised_date + pd.to_timedelta([1, 2, 2], unit="D")
    frame["is_late"] = 1  # must not override the shared labeling rule
    row = supplier_scorecard(frame).iloc[0]
    assert (row.on_time, row.late) == (2, 1)


def test_material_breakdown_rolls_up():
    frame = history()
    frame.loc[:4, "material_type"] = "cement"
    detail = material_breakdown(frame).set_index("material_type")
    assert set(detail.index) == {"cement", "ready_mix_concrete"}
    assert detail.loc["cement", "on_time"] == 3  # 1-day delay falls within cement grace
    assert detail.deliveries.sum() == supplier_scorecard(frame).iloc[0].deliveries
    assert detail.on_time.sum() == supplier_scorecard(frame).iloc[0].on_time


def test_missing_history_is_not_zero_performance():
    row = supplier_scorecard(history().iloc[5:]).iloc[0]
    assert row.on_time_share == 1
    assert pd.isna(row.median_late_days) and pd.isna(row.p90_late_days)
    assert pd.isna(row.previous_on_time_share) and pd.isna(row.trend_pp)


def test_recent_window_is_shared_by_suppliers():
    frame = history()
    frame.loc[:4, "supplier_id"] = "old-only"
    rows = supplier_scorecard(frame).set_index("supplier_id")
    assert rows.loc["old-only", "recent_deliveries"] == 0
    assert pd.isna(rows.loc["old-only", "recent_on_time_share"])
    assert pd.isna(rows.loc["old-only", "trend_pp"])


def test_ninety_day_boundary():
    frame = history().iloc[:3].copy()
    frame["promised_date"] = pd.to_datetime(["2026-07-03", "2026-07-04", "2026-10-01"])
    frame["actual_date"] = frame.promised_date
    row = supplier_scorecard(frame).iloc[0]
    assert (row.recent_deliveries, row.previous_deliveries) == (2, 1)


def test_empty_frame_preserves_output_columns():
    empty = history().iloc[:0]
    assert supplier_scorecard(empty).empty
    assert "on_time_ci_low" in supplier_scorecard(empty).columns
    assert "material_type" in material_breakdown(empty).columns


def test_invalid_history_is_rejected():
    with pytest.raises(ValueError, match="Missing scorecard columns"):
        supplier_scorecard(pd.DataFrame())
    for column in ("supplier_id", "material_type", "actual_date", "promised_date"):
        frame = history()
        frame.loc[0, column] = None
        with pytest.raises(ValueError):
            supplier_scorecard(frame)


def test_input_is_unchanged_and_order_is_deterministic():
    frame = history()
    before = frame.copy(deep=True)
    expected = supplier_scorecard(frame)
    pd.testing.assert_frame_equal(frame, before)
    pd.testing.assert_frame_equal(supplier_scorecard(frame.sample(frac=1, random_state=3)), expected)


def test_real_export_seam():
    frame, quality = load_export(Path(__file__).parent / "fixtures" / "1c_export_cp1251.csv")
    scorecard = supplier_scorecard(frame)
    assert scorecard.deliveries.sum() == quality.rows_kept
    assert scorecard.on_time.sum() + scorecard.late.sum() == quality.rows_kept
    assert scorecard.on_time_share.between(0, 1).all()
