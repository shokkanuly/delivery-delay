"""
Synthetic data generator for the construction logistics platform MVP.
Produces realistic Kazakhstan-flavored datasets for:
  1. Delay prediction        -> delay_prediction.csv
  2. Resource scheduling      -> resources.csv, projects.csv, booking_requests.csv
  3. Sequence validation      -> build_phases.csv, phase_material_map.csv, material_deliveries.csv

All datasets share the same project/supplier/material universe so they can
be joined and used together on one platform.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

rng = np.random.default_rng(42)

OUT = "/home/claude/synthetic_data"

# ---------------------------------------------------------------------------
# Shared universe: cities, projects, suppliers, materials
# ---------------------------------------------------------------------------

cities = ["Almaty", "Astana", "Shymkent", "Karagandy", "Aktobe", "Atyrau"]

project_names = [
    "Nurly Zhol Residence", "Alatau Towers", "Green Line Business Center",
    "Saryarka Housing Complex", "Caspian Waterfront", "Silk Road Mall",
    "Kokserek Park Residences", "Turan Business Hub", "Bereke Family Homes",
    "Zharyk Industrial Park"
]

projects = pd.DataFrame({
    "project_id": [f"PRJ_{i+1:03d}" for i in range(len(project_names))],
    "name": project_names,
    "location": rng.choice(cities, size=len(project_names)),
    "priority": rng.choice(["high", "medium", "low"], size=len(project_names), p=[0.3, 0.5, 0.2]),
    "start_date": pd.to_datetime("2026-01-01") + pd.to_timedelta(rng.integers(0, 60, len(project_names)), unit="D"),
})
projects["end_date"] = projects["start_date"] + pd.to_timedelta(rng.integers(180, 360, len(projects)), unit="D")

suppliers_data = [
    ("SUP_001", "Almaty Cement Zavod", 0.92, ["cement", "concrete_mix"]),
    ("SUP_002", "Kazrebar Steel",      0.78, ["rebar", "steel_beams"]),
    ("SUP_003", "Prefab KZ",           0.65, ["prefab_panels"]),
    ("SUP_004", "SteelImport Turkey",  0.55, ["steel_beams", "glass_facade"]),
    ("SUP_005", "Karagandy Insulate",  0.88, ["insulation"]),
    ("SUP_006", "Astana Glass Works",  0.81, ["glass_facade"]),
    ("SUP_007", "EcoBrick Shymkent",   0.90, ["bricks", "cement"]),
    ("SUP_008", "China Modular Import", 0.48, ["prefab_panels", "modular_units"]),
    ("SUP_009", "Atyrau Pipe & Steel", 0.73, ["rebar", "pipes"]),
    ("SUP_010", "Local Timber Co",     0.94, ["timber", "formwork"]),
]
suppliers = pd.DataFrame(suppliers_data, columns=["supplier_id", "supplier_name", "on_time_rate", "materials"])

all_materials = sorted(set(m for row in suppliers_data for m in row[3]))

# ---------------------------------------------------------------------------
# 1. DELAY PREDICTION DATASET
# ---------------------------------------------------------------------------

N_DELIV = 2200
rows = []
base_date = datetime(2025, 1, 1)

for i in range(N_DELIV):
    sup = suppliers.iloc[rng.integers(0, len(suppliers))]
    material = rng.choice(sup["materials"])
    proj = projects.iloc[rng.integers(0, len(projects))]

    order_date = base_date + timedelta(days=int(rng.integers(0, 540)))
    lead_time = int(rng.integers(3, 45))  # days between order and promised delivery
    promised_date = order_date + timedelta(days=lead_time)

    is_import = sup["supplier_name"].lower().find("import") >= 0 or sup["supplier_name"].lower().find("turkey") >= 0 or sup["supplier_name"].lower().find("china") >= 0
    route_type = "cross_border" if is_import else rng.choice(["urban", "intercity"], p=[0.4, 0.6])
    distance_km = {
        "urban": rng.integers(5, 60),
        "intercity": rng.integers(60, 900),
        "cross_border": rng.integers(800, 4500),
    }[route_type]

    month = promised_date.month
    season = "winter" if month in (12, 1, 2) else "summer" if month in (6, 7, 8) else "shoulder"
    weather_severity = rng.choice(["low", "medium", "high"],
                                   p=[0.5, 0.35, 0.15] if season != "winter" else [0.25, 0.40, 0.35])

    # --- ground-truth delay model (what the ML model should learn to approximate) ---
    base_late_prob = 1 - sup["on_time_rate"]
    season_bump = 0.18 if season == "winter" else 0.0
    weather_bump = {"low": 0.0, "medium": 0.08, "high": 0.22}[weather_severity]
    route_bump = {"urban": 0.0, "intercity": 0.06, "cross_border": 0.20}[route_type]
    short_lead_bump = 0.15 if lead_time < 7 else 0.0

    late_prob = min(0.95, base_late_prob + season_bump + weather_bump + route_bump + short_lead_bump)
    early_prob = 0.06 if lead_time > 20 else 0.03

    r = rng.random()
    if r < early_prob:
        status = "early"
        delay_days = -int(rng.integers(1, 5))
    elif r < early_prob + late_prob:
        status = "late"
        severity_scale = 2 + weather_bump * 20 + route_bump * 15
        delay_days = int(rng.integers(1, max(2, int(severity_scale) + 10)))
    else:
        status = "on_time"
        delay_days = 0

    actual_date = promised_date + timedelta(days=int(delay_days))
    quantity = int(rng.integers(10, 5000))

    rows.append({
        "delivery_id": f"DEL_{i+1:05d}",
        "supplier_id": sup["supplier_id"],
        "supplier_name": sup["supplier_name"],
        "material_type": material,
        "project_id": proj["project_id"],
        "project_site": proj["location"],
        "order_date": order_date.date().isoformat(),
        "promised_date": promised_date.date().isoformat(),
        "actual_date": actual_date.date().isoformat(),
        "lead_time_days": lead_time,
        "quantity": quantity,
        "route_type": route_type,
        "distance_km": int(distance_km),
        "season": season,
        "weather_severity": weather_severity,
        "supplier_on_time_rate_hist": round(float(sup["on_time_rate"]), 2),
        "delay_days": int(delay_days),
        "status": status,  # label: on_time / late / early
    })

delay_df = pd.DataFrame(rows)
delay_df.to_csv(f"{OUT}/delay_prediction.csv", index=False)

# ---------------------------------------------------------------------------
# 2. RESOURCE SCHEDULING DATASET
# ---------------------------------------------------------------------------

resource_types = ["truck", "crane", "crew"]
resources = []
rid = 1
for rtype, count in [("truck", 12), ("crane", 6), ("crew", 10)]:
    for _ in range(count):
        resources.append({
            "resource_id": f"RES_{rid:03d}",
            "type": rtype,
            "capacity": {"truck": rng.integers(5, 20), "crane": 1, "crew": rng.integers(4, 12)}[rtype],
            "home_location": rng.choice(cities),
        })
        rid += 1
resources_df = pd.DataFrame(resources)
resources_df.to_csv(f"{OUT}/resources.csv", index=False)

N_BOOKINGS = 260
bookings = []
for i in range(N_BOOKINGS):
    proj = projects.iloc[rng.integers(0, len(projects))]
    rtype = rng.choice(resource_types)
    start_offset = int(rng.integers(0, 300))
    duration_hours = int(rng.integers(4, 72))
    start_dt = datetime(2026, 1, 1) + timedelta(days=start_offset, hours=int(rng.integers(0, 8)))
    end_dt = start_dt + timedelta(hours=duration_hours)

    task = {
        "truck": rng.choice(["material delivery", "spoil removal", "equipment transport"]),
        "crane": rng.choice(["panel lift", "steel beam placement", "prefab assembly"]),
        "crew": rng.choice(["formwork", "concrete pour", "finishing works", "electrical rough-in"]),
    }[rtype]

    bookings.append({
        "booking_id": f"BK_{i+1:04d}",
        "project_id": proj["project_id"],
        "project_priority": proj["priority"],
        "resource_type": rtype,
        "requested_start": start_dt.isoformat(),
        "requested_end": end_dt.isoformat(),
        "task": task,
        "assigned_resource_id": "",  # left blank on purpose: this is what the CP-SAT solver should fill in
    })

bookings_df = pd.DataFrame(bookings)
bookings_df.to_csv(f"{OUT}/booking_requests.csv", index=False)
projects.to_csv(f"{OUT}/projects.csv", index=False)

# ---------------------------------------------------------------------------
# 3. SEQUENCE VALIDATION DATASET
# ---------------------------------------------------------------------------

phase_order = [
    "site_prep", "foundation", "structural_frame", "envelope_facade",
    "mep_rough_in", "insulation_drywall", "finishing", "handover"
]

phase_material_map = {
    "site_prep": ["formwork", "timber"],
    "foundation": ["cement", "rebar", "concrete_mix"],
    "structural_frame": ["steel_beams", "rebar", "prefab_panels", "modular_units"],
    "envelope_facade": ["bricks", "glass_facade", "cement"],
    "mep_rough_in": ["pipes"],
    "insulation_drywall": ["insulation"],
    "finishing": ["glass_facade", "insulation"],
    "handover": [],
}
pmm_rows = [{"phase_name": k, "required_materials": ";".join(v)} for k, v in phase_material_map.items()]
pd.DataFrame(pmm_rows).to_csv(f"{OUT}/phase_material_map.csv", index=False)

build_phases = []
for _, proj in projects.iterrows():
    phase_start = proj["start_date"]
    for order, phase in enumerate(phase_order):
        dur = int(rng.integers(10, 35))
        phase_end = phase_start + timedelta(days=dur)
        build_phases.append({
            "project_id": proj["project_id"],
            "phase_name": phase,
            "phase_order": order,
            "start_date": phase_start.date().isoformat(),
            "end_date": phase_end.date().isoformat(),
        })
        phase_start = phase_end
build_phases_df = pd.DataFrame(build_phases)
build_phases_df.to_csv(f"{OUT}/build_phases.csv", index=False)

# Material deliveries mapped against phases, with ~15% deliberately mis-sequenced
seq_rows = []
seq_id = 1
for _, proj in projects.iterrows():
    proj_phases = build_phases_df[build_phases_df["project_id"] == proj["project_id"]].reset_index(drop=True)
    n_deliveries = int(rng.integers(15, 30))
    for _ in range(n_deliveries):
        phase_row = proj_phases.iloc[rng.integers(0, len(proj_phases))]
        required_materials = phase_material_map[phase_row["phase_name"]]
        if not required_materials:
            material = rng.choice(all_materials)
        else:
            material = rng.choice(required_materials)

        phase_start = pd.to_datetime(phase_row["start_date"])
        phase_end = pd.to_datetime(phase_row["end_date"])

        is_error = rng.random() < 0.15
        if is_error:
            # delivered before the phase even starts (or during an unrelated earlier phase)
            delivery_date = phase_start - timedelta(days=int(rng.integers(5, 40)))
            error_flag = "premature_delivery"
        else:
            delivery_date = phase_start + timedelta(
                days=int(rng.integers(0, max(1, (phase_end - phase_start).days)))
            )
            error_flag = ""

        seq_rows.append({
            "delivery_seq_id": f"SEQ_{seq_id:05d}",
            "project_id": proj["project_id"],
            "material_type": material,
            "required_phase": phase_row["phase_name"],
            "delivery_date": delivery_date.date().isoformat(),
            "phase_start_date": phase_row["start_date"],
            "phase_end_date": phase_row["end_date"],
            "flag": error_flag,  # ground-truth label for validation
        })
        seq_id += 1

seq_df = pd.DataFrame(seq_rows)
seq_df.to_csv(f"{OUT}/material_deliveries.csv", index=False)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("Generated files:")
for fname, df in [
    ("delay_prediction.csv", delay_df),
    ("resources.csv", resources_df),
    ("projects.csv", projects),
    ("booking_requests.csv", bookings_df),
    ("build_phases.csv", build_phases_df),
    ("phase_material_map.csv", pd.DataFrame(pmm_rows)),
    ("material_deliveries.csv", seq_df),
]:
    print(f"  {fname}: {len(df)} rows")

print("\nDelay prediction label distribution:")
print(delay_df["status"].value_counts(normalize=True).round(3))

print("\nSequence validation flag distribution:")
print(seq_df["flag"].replace("", "none").value_counts(normalize=True).round(3))
