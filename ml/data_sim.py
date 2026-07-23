"""Synthetic delivery data generator.

Produces ONLY the columns you would actually have at order time, plus the
realized `actual_date`. It deliberately does NOT emit any pre-aggregated
supplier/material statistics -- those must be derived causally in features.py,
otherwise you leak the future into the past (see Problem 2).

The generative process gives the model real signal to learn (supplier quality,
material, route, season, lead time) plus irreducible noise, and it introduces
some brand-new suppliers late in the timeline so the cold-start path (Problem 3)
is actually exercised.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# material -> baseline delay tendency in days (harder-to-source => later)
MATERIALS = {
    "ready_mix_concrete": 0.4,
    "cement": 0.9,
    "rebar": 1.3,
    "insulation": 1.6,
    "bricks": 1.9,
    "tiles_finishing": 2.3,
}
# route -> added delay tendency in days
ROUTES = {"urban": 0.0, "intercity": 1.1, "cross_border": 2.6}
ROUTE_MIX = [0.55, 0.35, 0.10]  # how often each route occurs

PROJECT_SITES = ["astana_north", "astana_south", "almaty_ring", "shymkent_hub"]

# Realized winter severity by month (Kazakhstan): drives extra delay in the sim.
_SIM_MONTH_SEVERITY = {
    1: 2.4, 2: 2.0, 3: 1.0, 4: 0.4, 5: 0.1, 6: 0.0,
    7: 0.0, 8: 0.0, 9: 0.2, 10: 0.7, 11: 1.2, 12: 2.1,
}


def generate_deliveries(
    n: int = 1200,
    n_suppliers: int = 25,
    seed: int = 7,
    start: str = "2024-01-01",
    horizon_days: int = 540,
) -> pd.DataFrame:
    """Return a DataFrame of raw delivery records sorted by order_date."""
    rng = np.random.default_rng(seed)

    # Latent, unobserved supplier reliability. The model never sees these; it can
    # only estimate them from history -- which is the whole point of the baseline.
    supplier_offset = rng.normal(0.0, 1.3, n_suppliers)     # chronic early/late bias
    supplier_noise = rng.uniform(0.6, 2.2, n_suppliers)     # consistency

    # ~30% of suppliers only appear partway through the timeline (cold start).
    n_established = int(round(n_suppliers * 0.7))
    first_active_frac = np.zeros(n_suppliers)
    first_active_frac[n_established:] = rng.uniform(0.55, 0.9, n_suppliers - n_established)

    start_ts = pd.Timestamp(start)
    materials = list(MATERIALS)
    routes = list(ROUTES)

    rows = []
    for _ in range(n):
        t_frac = rng.random()
        order_date = start_ts + pd.Timedelta(days=int(t_frac * horizon_days))

        active = np.where(first_active_frac <= t_frac)[0]
        supplier = int(rng.choice(active))

        material = str(rng.choice(materials))
        route = str(rng.choice(routes, p=ROUTE_MIX))
        site = str(rng.choice(PROJECT_SITES))
        quantity = int(rng.integers(5, 200))
        lead_time = int(rng.integers(2, 45))
        promised_date = order_date + pd.Timedelta(days=lead_time)

        month = promised_date.month
        season = _SIM_MONTH_SEVERITY.get(month, 0.0)
        short_lead_penalty = max(0.0, 10 - lead_time) * 0.15  # rush orders slip more

        mean_delay = (
            MATERIALS[material]
            + ROUTES[route]
            + supplier_offset[supplier]
            + season
            + short_lead_penalty
        )
        delay_days = int(round(rng.normal(mean_delay, supplier_noise[supplier])))
        actual_date = promised_date + pd.Timedelta(days=delay_days)
        # A delivery cannot physically arrive before it was ordered.
        if actual_date < order_date:
            actual_date = order_date

        rows.append(
            {
                "supplier_id": f"S{supplier:02d}",
                "project_site": site,
                "material_type": material,
                "route_type": route,
                "quantity": quantity,
                "order_date": order_date,
                "promised_date": promised_date,
                "actual_date": actual_date,
            }
        )

    df = pd.DataFrame(rows).sort_values("order_date").reset_index(drop=True)
    df.insert(0, "delivery_id", range(1, len(df) + 1))
    return df


if __name__ == "__main__":
    d = generate_deliveries()
    print(d.head(8).to_string(index=False))
    print(f"\n{len(d)} rows | {d['supplier_id'].nunique()} suppliers "
          f"| {d['order_date'].min().date()} -> {d['order_date'].max().date()}")
