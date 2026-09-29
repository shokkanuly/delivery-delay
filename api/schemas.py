"""Pydantic request/response contracts for the API."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class DeliveryIn(BaseModel):
    """One delivery to score. These are exactly ml.predict.REQUIRED_FIELDS."""

    supplier_id: str
    material_type: str
    route_type: str
    quantity: int = Field(gt=0)
    order_date: date
    promised_date: date

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


class CompanyWorkspaceIn(BaseModel):
    access_key: str
    company_name: str
    project_id: str
    project_name: str
    location: str
    building_type: str = "Residential High-Rise"
    total_area_sqm: float = 45000.0
    floors: int = 18
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

