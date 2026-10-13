"""Business economics -- the single source of truth for every pitch number.

Every figure a juror or customer sees (per-site ROI, unit economics, the
3-year forecast, market size) is computed here from the assumptions below.
The API serves it (`GET /economics`, workspace finance), both UIs render what
the API returns, and tests/test_pitch_claims.py fails if README or the deck
quote a figure this module does not produce.

Every assumption carries its provenance, because the first jury question about
any number is "where does that come from?":
  founder_estimate -- the founder's judgement, not yet checked against data
  interview        -- stated in customer interviews (docs/CUSTDEV_LOG.md)
  demo_site        -- inputs of the fictional demo Site B
Nothing here is measured on a real site yet. The pilot replaces these.

Design choices:
  * Per-site value is shown as three scenarios, never one number. The base
    case is anchored to the founder's own interview figure (concrete loss
    ~$28k per project) and Q&A answer (5 delay days avoided); the
    conservative case shows whether the product still pays for itself.
  * LTV is gross-margin-adjusted and bounded by the site's life: revenue per
    site stops at handover, so there is no net-revenue-retention claim.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Assumption:
    value: float
    unit: str
    source: str          # founder_estimate | interview | demo_site
    note: str = ""


ASSUMPTIONS: dict[str, Assumption] = {
    # --- pricing ---
    "price_per_site_month": Assumption(
        3500, "USD/site/month", "founder_estimate",
        "Standard site tier: up to 4 cranes, 500 deliveries/month."),
    "price_mega_site_month": Assumption(
        4800, "USD/site/month", "founder_estimate",
        "Flagship tier: >4 cranes, >1,000 deliveries/month."),
    "pilot_fee": Assumption(
        15000, "USD", "founder_estimate",
        "8-week, 2-site pilot; credited against the first annual contract."),
    # --- unit economics ---
    "gross_margin": Assumption(
        0.75, "share", "founder_estimate",
        "Below pure-SaaS levels: on-prem/private-cloud installs and 1C "
        "integration are support work per customer."),
    "site_lifetime_months": Assumption(
        24, "months", "founder_estimate",
        "Active logistics phase of a high-rise build; revenue for a site "
        "ends at handover."),
    "cac_per_site": Assumption(
        15000, "USD", "founder_estimate",
        "Blended founder-led enterprise sale, 3-4 month cycle, pilot support."),
    "monthly_opex": Assumption(
        21000, "USD/month", "founder_estimate",
        "Team + infrastructure run-rate used for break-even."),
    # --- market (site counts are unsourced until checked) ---
    "beachhead_sites": Assumption(
        180, "active sites", "founder_estimate",
        "Active major sites of the top-15 developer holdings in KZ and UZ."),
    "regional_sites": Assumption(
        3200, "active sites", "founder_estimate",
        "Major multi-storey sites across Central Asia, Caucasus and CIS."),
}

# Paid active sites at the end of years 1-3. The ONE forecast.
FORECAST_SITES: tuple[int, int, int] = (4, 17, 35)

# Per-site value levers, by scenario.
SCENARIOS: dict[str, dict[str, float]] = {
    "conservative": {"crane_idle_days_per_crane": 1, "concrete_loss_share": 0.005,
                     "delay_days_avoided": 2},
    "base":         {"crane_idle_days_per_crane": 2, "concrete_loss_share": 0.01,
                     "delay_days_avoided": 5},
    "upside":       {"crane_idle_days_per_crane": 4, "concrete_loss_share": 0.02,
                     "delay_days_avoided": 10},
}

# Numeric inputs of the fictional demo Site B (Astana, 24 floors, 6 cranes).
DEMO_SITE_INPUTS: dict = {
    "start_date": "2026-02-15",
    "target_end_date": "2026-12-20",
    "cranes_count": 6,
    "pumps_count": 3,
    "hoists_count": 4,
    "rebar_tons": 4500.0,
    "concrete_m3": 21000.0,
    "crane_daily_rate": 1600.0,
    "delay_penalty_per_day": 12000.0,
    "concrete_cost_m3": 115.0,
    "total_logistics_budget": 3500000.0,
}


def _a(name: str) -> float:
    return ASSUMPTIONS[name].value


def annual_licence() -> float:
    return _a("price_per_site_month") * 12


def _duration_days(site: dict) -> int:
    from datetime import datetime
    try:
        d1 = datetime.strptime(str(site["start_date"])[:10], "%Y-%m-%d")
        d2 = datetime.strptime(str(site["target_end_date"])[:10], "%Y-%m-%d")
        return max(30, (d2 - d1).days)
    except (KeyError, ValueError):
        return 270


def site_value(site: dict, scenario: str) -> dict:
    """Losses avoided on one site in one year, for one scenario."""
    lever = SCENARIOS[scenario]
    cranes = site.get("cranes_count", 4)
    crane_rate = site.get("crane_daily_rate", 1500.0)
    concrete_value = site.get("concrete_m3", 14500.0) * site.get("concrete_cost_m3", 110.0)
    budget = site.get("total_logistics_budget", 2400000.0)

    crane = cranes * crane_rate * lever["crane_idle_days_per_crane"]
    concrete = concrete_value * lever["concrete_loss_share"]
    delay = site.get("delay_penalty_per_day", 8500.0) * lever["delay_days_avoided"]
    total = crane + concrete + delay
    return {
        "crane_idle_avoided": round(crane, 2),
        "concrete_loss_avoided": round(concrete, 2),
        "delay_penalty_avoided": round(delay, 2),
        "total_value": round(total, 2),
        "value_multiple": round(total / annual_licence(), 2),
        "share_of_logistics_budget": round(total / max(1.0, budget), 4),
    }


def site_finance(site: dict) -> dict:
    """Workspace finance: site cost context plus value in every scenario."""
    duration = _duration_days(site)
    cranes = site.get("cranes_count", 4)
    pumps = site.get("pumps_count", 2)
    crane_rate = site.get("crane_daily_rate", 1500.0)
    machinery = (cranes * crane_rate + pumps * crane_rate * 0.7) * (duration * 0.7)
    return {
        "duration_days": duration,
        "machinery_est_cost": round(machinery, 2),
        "concrete_total_val": round(site.get("concrete_m3", 14500.0)
                                    * site.get("concrete_cost_m3", 110.0), 2),
        "annual_licence": annual_licence(),
        "scenarios": {name: site_value(site, name) for name in SCENARIOS},
    }


def unit_economics() -> dict:
    gp_month = _a("price_per_site_month") * _a("gross_margin")
    ltv = gp_month * _a("site_lifetime_months")
    return {
        "acv": annual_licence(),
        "gross_margin": _a("gross_margin"),
        "gross_profit_per_site_month": gp_month,
        "ltv": ltv,
        "cac": _a("cac_per_site"),
        "ltv_to_cac": round(ltv / _a("cac_per_site"), 1),
        "cac_payback_months": round(_a("cac_per_site") / gp_month, 1),
        "break_even_sites": math.ceil(_a("monthly_opex") / gp_month),
    }


def forecast() -> dict:
    years = [{"year": i + 1, "sites": s, "arr": s * annual_licence()}
             for i, s in enumerate(FORECAST_SITES)]
    return {"years": years, "break_even_month": _break_even_month()}


def _break_even_month() -> int | None:
    """First month the paid-site count reaches break-even, interpolating the
    forecast linearly from 0 sites at month 0."""
    target = unit_economics()["break_even_sites"]
    points = [(0, 0)] + [(12 * (i + 1), s) for i, s in enumerate(FORECAST_SITES)]
    for (m0, s0), (m1, s1) in zip(points, points[1:]):
        if s1 >= target:
            return math.ceil(m0 + (target - s0) / (s1 - s0) * (m1 - m0))
    return None


def market() -> dict:
    acv = annual_licence()
    y3_sites = FORECAST_SITES[-1]
    return {
        "regional": _a("regional_sites") * acv,
        "beachhead": _a("beachhead_sites") * acv,
        "year3_arr": y3_sites * acv,
        "year3_share_of_beachhead": round(y3_sites / _a("beachhead_sites"), 3),
    }


def _money(x: float) -> str:
    if x >= 100_000_000:
        return f"${x / 1_000_000:.0f}M"
    if x >= 1_000_000:
        return f"${x / 1_000_000:.2f}M".replace(".00M", "M")
    if x >= 1_000:
        return f"${x / 1_000:,.0f}k"
    return f"${x:,.0f}"


def headline() -> dict[str, str]:
    """Display strings quoted verbatim by README, the deck and the UIs."""
    ue, fc, mk = unit_economics(), forecast(), market()
    demo = site_finance(DEMO_SITE_INPUTS)["scenarios"]
    out = {
        "price": f"${_a('price_per_site_month'):,.0f} / site / month",
        "price_range": f"${_a('price_per_site_month'):,.0f} – ${_a('price_mega_site_month'):,.0f} / site / month",
        "acv": _money(ue["acv"]),
        "pilot_fee": _money(_a("pilot_fee")),
        "gross_margin": f"{ue['gross_margin']:.0%}",
        "ltv": _money(ue["ltv"]),
        "cac": _money(ue["cac"]),
        "ltv_to_cac": f"{ue['ltv_to_cac']:.1f} : 1",
        "cac_payback": f"{ue['cac_payback_months']:.1f} months",
        "break_even": f"month {fc['break_even_month']} ({ue['break_even_sites']} paid sites)",
        "market_regional": _money(mk["regional"]),
        "market_beachhead": _money(mk["beachhead"]),
        "year3_share": f"{mk['year3_share_of_beachhead']:.0%}",
    }
    for y in fc["years"]:
        out[f"y{y['year']}"] = f"{y['sites']} sites · {_money(y['arr'])} ARR"
    for name, v in demo.items():
        out[f"value_{name}"] = _money(v["total_value"])
        out[f"multiple_{name}"] = f"{v['value_multiple']:.1f}×"
        out[f"budget_share_{name}"] = f"{v['share_of_logistics_budget']:.1%}"
    return out


def summary() -> dict:
    """Everything, for `GET /economics`."""
    return {
        "assumptions": {k: asdict(v) for k, v in ASSUMPTIONS.items()},
        "scenarios": SCENARIOS,
        "demo_site": {"inputs": DEMO_SITE_INPUTS,
                      "finance": site_finance(DEMO_SITE_INPUTS)},
        "unit_economics": unit_economics(),
        "forecast": forecast(),
        "market": market(),
        "headline": headline(),
    }
