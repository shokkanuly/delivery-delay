"""Pydantic request/response contracts for the API."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class DeliveryIn(BaseModel):
    """One delivery to score. These are exactly ml.predict.REQUIRED_FIELDS."""

    supplier_id: str
    material_type: str
    route_type: str
    quantity: int = Field(gt=0)
    order_date: date
    promised_date: date
    # Optional: your own delivery id (1C order line, waybill). Logged, not a model feature, so a later gate
    # arrival or POST /outcomes can be matched to this prediction.
    delivery_ref: str | None = Field(None, max_length=64)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "supplier_id": "S07",
                    "material_type": "ready_mix_concrete",
                    "route_type": "cross_border",
                    "quantity": 120,
                    "order_date": "2025-01-05",
                    "promised_date": "2025-01-12",
                }
            ]
        }
    }


class Driver(BaseModel):
    factor: str
    value: str
    impact: float


class PredictionOut(BaseModel):
    risk: float
    risk_band: str            # green | yellow | red
    supplier_late_rate: float
    supplier_n_prior: int
    lead_time_days: int
    # "if it slips, by how much" — check /metrics.delay_days_head.beats_baseline
    # before presenting this as a firm estimate.
    expected_delay_days: float | None = None
    drivers: list[Driver]


class SiteInputsIn(BaseModel):
    """Numeric site inputs that business.economics.site_finance reads."""
    start_date: str = "2026-03-01"
    target_end_date: str = "2026-11-30"
    # Logistics
    cranes_count: int = 4
    pumps_count: int = 2
    hoists_count: int = 3
    rebar_tons: float = 3200.0
    concrete_m3: float = 14500.0
    # Finance
    crane_daily_rate: float = 1500.0
    delay_penalty_per_day: float = 8500.0
    concrete_cost_m3: float = 110.0
    total_logistics_budget: float = 2400000.0


class CompanyWorkspaceIn(SiteInputsIn):
    access_key: str = ""   # blank on create: the server issues a key
    company_name: str
    project_id: str
    project_name: str
    location: str
    building_type: str = "Residential High-Rise"
    total_area_sqm: float = 45000.0
    floors: int = 18


class AuditQualityOut(BaseModel):
    rows_total: int
    rows_kept: int
    rows_dropped: int
    bad_dates: int
    bad_quantity: int
    duplicates: int
    promised_before_order: int
    route_type_defaulted: int
    material_grace_defaulted: int
    unmapped_columns: list[str]


class SupplierScorecardOut(BaseModel):
    supplier_id: str
    material_type: str | None = None
    deliveries: int
    on_time: int
    late: int
    on_time_share: float
    on_time_ci_low: float
    on_time_ci_high: float
    median_late_days: float | None
    p90_late_days: float | None
    recent_deliveries: int
    previous_deliveries: int
    recent_on_time_share: float | None
    previous_on_time_share: float | None
    trend_pp: float | None


class AuditBandOut(BaseModel):
    deliveries: int
    late_rate: float | None


class HistoryBacktestOut(BaseModel):
    status: Literal["evaluated", "insufficient_data"]
    reason: str | None
    train_rows: int
    test_rows: int
    excluded_chronology: int
    purged_train_rows: int
    cutoff: str | None
    train_order_max: str | None
    train_actual_max: str | None
    test_order_min: str | None
    model_average_precision: float | None
    baseline_average_precision: float | None
    lift: float | None
    beats_baseline: bool | None
    risk_bands: dict[str, AuditBandOut]


class HistoryAuditOut(BaseModel):
    data_source: Literal["synthetic_upload", "uploaded_unverified"]
    quality: AuditQualityOut
    scorecard: list[SupplierScorecardOut]
    material_breakdown: list[SupplierScorecardOut]
    backtest: HistoryBacktestOut
    notes: list[str]
    saved: bool = False
    audit_id: str | None = None
