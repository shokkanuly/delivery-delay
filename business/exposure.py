"""Exposure in tenge (Stage 4, docs/plans/mvp-reshape.md D8): value stated with
the customer's own contract and downtime numbers only -- no USD, no scenario
assumption, no founder estimate (contrast with business/economics.py, which is
the pitch-deck model). Every input is the customer's; there is no default to
fall back to, so a missing one is a 422 at the API boundary, not a guess here.
"""
from __future__ import annotations


def exposure(contract_value_kzt: float, late_penalty_rate: float, days_late: float,
             downtime_hours: float, downtime_cost_per_hour_kzt: float) -> dict:
    """Two independent exposures, summed: the contract's own late-delivery
    penalty clause (value x rate x days), and idle-crew/equipment cost during
    the delay (hours x hourly rate). Both read straight from the customer's
    figures -- nothing here is a model prediction or a scenario."""
    penalty_exposure_kzt = contract_value_kzt * late_penalty_rate * days_late
    downtime_exposure_kzt = downtime_hours * downtime_cost_per_hour_kzt
    total_exposure_kzt = penalty_exposure_kzt + downtime_exposure_kzt
    return {
        "penalty_exposure_kzt": round(penalty_exposure_kzt, 2),
        "downtime_exposure_kzt": round(downtime_exposure_kzt, 2),
        "total_exposure_kzt": round(total_exposure_kzt, 2),
    }
