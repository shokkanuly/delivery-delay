"""Stage 4 (docs/plans/mvp-reshape.md): business/exposure.py and
POST /economics/exposure. Known-answer: 50,000,000 (tenge) x 0.1% x 4 days +
6h x 25,000 (tenge/h) = 350,000 (tenge)."""
from __future__ import annotations

from business import exposure as e


def test_known_answer():
    result = e.exposure(
        contract_value_kzt=50_000_000,
        late_penalty_rate=0.001,
        days_late=4,
        downtime_hours=6,
        downtime_cost_per_hour_kzt=25_000,
    )
    assert result["penalty_exposure_kzt"] == 200_000
    assert result["downtime_exposure_kzt"] == 150_000
    assert result["total_exposure_kzt"] == 350_000


def test_zero_days_late_or_downtime_contributes_nothing():
    result = e.exposure(
        contract_value_kzt=10_000_000,
        late_penalty_rate=0.002,
        days_late=0,
        downtime_hours=0,
        downtime_cost_per_hour_kzt=30_000,
    )
    assert result["total_exposure_kzt"] == 0


class TestExposureEndpoint:
    def test_matches_the_module(self, api_client):
        payload = {
            "contract_value_kzt": 50_000_000,
            "late_penalty_rate": 0.001,
            "days_late": 4,
            "downtime_hours": 6,
            "downtime_cost_per_hour_kzt": 25_000,
        }
        body = api_client.post("/economics/exposure", json=payload).json()
        assert body == e.exposure(**payload)
        assert body["total_exposure_kzt"] == 350_000

    def test_missing_input_is_422_naming_the_field(self, api_client):
        payload = {
            "contract_value_kzt": 50_000_000,
            "late_penalty_rate": 0.001,
            "days_late": 4,
            # downtime_hours missing
            "downtime_cost_per_hour_kzt": 25_000,
        }
        r = api_client.post("/economics/exposure", json=payload)
        assert r.status_code == 422
        fields = {tuple(err["loc"]) for err in r.json()["detail"]}
        assert ("body", "downtime_hours") in fields
