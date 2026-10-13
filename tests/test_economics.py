"""business/economics.py is the single source of every pitch number, so these
tests pin the invariants a juror would check by hand."""
from __future__ import annotations

from business import economics as e


def test_every_assumption_has_provenance():
    allowed = {"founder_estimate", "interview", "demo_site"}
    for name, a in e.ASSUMPTIONS.items():
        assert a.source in allowed, name
        assert a.unit, name


def test_ltv_is_margin_adjusted_and_bounded_by_site_life():
    ue = e.unit_economics()
    price = e.ASSUMPTIONS["price_per_site_month"].value
    months = e.ASSUMPTIONS["site_lifetime_months"].value
    assert ue["ltv"] < price * months, "LTV must not be raw revenue"
    assert ue["ltv"] == price * e.ASSUMPTIONS["gross_margin"].value * months


def test_payback_and_ratio_follow_from_the_same_inputs():
    ue = e.unit_economics()
    assert ue["ltv_to_cac"] == round(ue["ltv"] / ue["cac"], 1)
    assert ue["cac_payback_months"] == round(ue["cac"] / ue["gross_profit_per_site_month"], 1)


def test_scenarios_are_ordered():
    s = e.site_finance(e.DEMO_SITE_INPUTS)["scenarios"]
    assert s["conservative"]["total_value"] < s["base"]["total_value"] < s["upside"]["total_value"]


def test_base_case_stays_plausible():
    """The old deck claimed ~18% of the site's whole logistics budget saved.
    Keep every scenario to a share a site director would believe."""
    for v in e.site_finance(e.DEMO_SITE_INPUTS)["scenarios"].values():
        assert v["share_of_logistics_budget"] < 0.08


def test_one_forecast_and_break_even_inside_it():
    fc = e.forecast()
    sites = [y["sites"] for y in fc["years"]]
    assert sites == sorted(sites)
    assert fc["break_even_month"] is not None
    assert 12 < fc["break_even_month"] <= 36


def test_market_share_is_not_full_capture():
    assert e.market()["year3_share_of_beachhead"] < 0.5


def test_economics_endpoint_matches_module():
    from fastapi.testclient import TestClient

    from api.main import app
    body = TestClient(app).get("/economics").json()
    assert body["headline"] == e.headline()
    assert set(body["demo_site"]["finance"]["scenarios"]) == set(e.SCENARIOS)
