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
