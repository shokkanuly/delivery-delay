"""Engine 3 — deterministic rules, so these are correctness checks on the date
logic rather than model evaluation."""
from __future__ import annotations

import pandas as pd

from engines.validator import (
    evaluate_against_truth,
    load_phase_material_map,
    validate_deliveries,
)
from engines.validator.rules import MISMATCH, PREMATURE


def test_perfect_recall_against_ground_truth(platform_data):
    s = validate_deliveries(platform_data["deliveries"],
                            phase_map=load_phase_material_map(platform_data["phase_map"]),
                            build_phases=platform_data["phases"])
    m = evaluate_against_truth(s)
    assert m["recall"] == 1.0, "must catch every known premature delivery"
    assert m["precision"] == 1.0, "must not invent premature deliveries"


def test_blank_allowlist_means_unconstrained(platform_data):
    """`handover` lists no materials. That means "not restricted", NOT "deny
    all" -- reading it as deny-all false-positived every handover delivery."""
    pm = load_phase_material_map(platform_data["phase_map"])
    assert pm["handover"] == set()

    s = validate_deliveries(platform_data["deliveries"], phase_map=pm,
                            build_phases=platform_data["phases"])
    assert s.counts[MISMATCH] == 0


def _delivery(delivery_date, phase_start, material="cement", phase="foundation"):
    return pd.DataFrame([{
        "delivery_seq_id": "X1", "project_id": "P1", "material_type": material,
        "required_phase": phase, "delivery_date": delivery_date,
        "phase_start_date": phase_start, "phase_end_date": "2026-04-01"}])


def test_flags_delivery_before_phase_start():
    s = validate_deliveries(_delivery("2026-03-01", "2026-03-10"))
    assert s.rows[0]["predicted_flag"] == PREMATURE
    assert "9 day(s)" in s.rows[0]["reason"]


def test_delivery_on_phase_start_is_clean():
    """Boundary: arriving exactly on the start date is on time, not early."""
    s = validate_deliveries(_delivery("2026-03-10", "2026-03-10"))
    assert s.rows[0]["predicted_flag"] is None


def test_material_not_allowed_for_phase():
    s = validate_deliveries(_delivery("2026-03-15", "2026-03-10", material="timber"),
                            phase_map={"foundation": {"cement", "rebar"}})
    assert s.rows[0]["predicted_flag"] == MISMATCH


def test_missing_columns_raise():
    import pytest
    with pytest.raises(ValueError, match="missing required columns"):
        validate_deliveries(pd.DataFrame([{"project_id": "P1"}]))
