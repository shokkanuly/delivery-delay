# Synthetic datasets — construction logistics platform MVP

All files share the same universe of 10 projects, 10 suppliers, and a fixed
material catalogue, so they can be joined across modules. Random seed = 42
(regenerate with `generate_synthetic_data.py` for a different draw).

## 1. Delay prediction — `delay_prediction.csv` (2,200 rows)

One row per delivery. Ground-truth delay/early/on-time label was generated
from a hidden formula combining supplier reliability, season, weather,
route type, and lead time — a LightGBM/XGBoost model trained on this should
recover roughly that structure, which is useful for validating your pipeline
before real data arrives.

| Column | Description |
|---|---|
| supplier_on_time_rate_hist | Supplier's historical reliability (0–1) |
| lead_time_days | Days between order and promised delivery |
| route_type | urban / intercity / cross_border |
| season, weather_severity | Context features |
| delay_days | Ground truth: negative = early, 0 = on time, positive = late |
| status | Label to predict: on_time / late / early |

Class balance: ~50% on_time, ~45% late, ~4% early — imbalanced toward late,
which matches the real-world pattern you'd expect to pitch against.

## 2. Resource scheduling — `resources.csv`, `projects.csv`, `booking_requests.csv`

- `resources.csv`: 28 resources (12 trucks, 6 cranes, 10 crews) with home city and capacity.
- `booking_requests.csv`: 260 booking requests across 10 projects, with
  overlapping time windows by design — this is the conflict data your
  OR-Tools CP-SAT model should resolve. `assigned_resource_id` is left blank
  intentionally; that's the column your solver fills in.

## 3. Sequence validation — `build_phases.csv`, `phase_material_map.csv`, `material_deliveries.csv`

- `build_phases.csv`: 8 phases per project (site_prep → handover) with dates.
- `phase_material_map.csv`: which material types belong to which phase (domain rule table).
- `material_deliveries.csv`: 219 deliveries mapped to a phase, ~12% flagged
  `premature_delivery` (arrived before their phase started) as ground truth
  for validating your rules engine.

## Suggested first steps

1. Delay prediction: train/test split on `delay_prediction.csv`, compare
   LightGBM against the naive baseline ("use supplier_on_time_rate_hist alone").
2. Resource scheduler: feed `booking_requests.csv` + `resources.csv` into
   OR-Tools CP-SAT; check how many of the built-in overlaps it resolves.
3. Sequence validator: run your rules engine against `material_deliveries.csv`
   and check recall/precision against the `flag` column.

All three should be swapped for real BI Group data as soon as it's available —
this synthetic data is for building and demoing the pipeline, not for the
final pilot claims.
