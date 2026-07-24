# Delivery-Delay Prediction — MVP (BI Group)

Flags construction-material deliveries likely to arrive **late** *before* they do,
with a per-delivery "why" and an honest baseline comparison. Three layers:

```
[CSV / Postgres] → [causal features] → [model + snapshot] → [FastAPI] → [Streamlit dashboard]
      Data                     ML                                    Application
```

The model **provably beats the supplier-average baseline** (5-fold CV: PR-AUC
0.86 vs 0.73, +0.13 lift with a CI clear of zero) and every risk score comes with
its top risk drivers.

---

## Quickstart — local (SQLite, zero setup)

Commands use `python3` (macOS ships no bare `python`).

```bash
python3 -m pip install -r requirements.txt
```
```bash
python3 -m db.seed
```
```bash
python3 -m ml.train
```
```bash
python3 -m uvicorn api.main:app --reload
```

API + interactive docs: http://localhost:8000/docs

In a second terminal:

```bash
python3 -m streamlit run dashboard/app.py
```

Dashboard: http://localhost:8501

**Shortcut:** `./start.sh` ensures a trained model, then starts the API and
dashboard together (Ctrl-C stops both).

## Quickstart — Docker (Postgres, full stack)

```bash
cp .env.example .env
docker compose up --build
```

Compose starts Postgres, seeds it, trains the model, then serves the API
(`:8000`) and dashboard (`:8501`).

## Verify the ML core on its own

```bash
python3 run.py
```
```bash
python3 -m ml.predict
```
`run.py` prints the four-problem correctness report (below); `ml.predict` scores
sample deliveries with their "why" drivers.

---

## Project layout

```
ml/         data_sim · labeling · features · baseline · train · predict   (+ artifacts/)
db/         models.py (SQLAlchemy) · database.py · seed.py
api/        main.py (FastAPI) · schemas.py
dashboard/  app.py (Streamlit)
run.py      ML-correctness demo        ROADMAP.md   build stages + status
Dockerfile  docker-compose.yml  .env.example
```

## API

| Method | Path | Purpose |
|---|---|---|
| GET  | `/health` | liveness + model info |
| GET  | `/metrics` | CV model-vs-baseline scorecard |
| POST | `/predict` | score one delivery → risk + drivers |
| POST | `/predict/batch` | score an uploaded CSV |
| GET  | `/deliveries/{project_id}` | a project's deliveries, risk-sorted |
| POST | `/train` | retrain and hot-swap the served model |

Interactive docs at `/docs`. Required fields for scoring:
`supplier_id, material_type, route_type, quantity, order_date, promised_date`.

---

## The ML-correctness core (why the numbers are trustworthy)

Four issues sink most delivery-delay demos. Each is solved and demonstrated by
`python run.py`:

| # | Problem | Fix | File |
|---|---------|-----|------|
| 4 | **Label** — "late" isn't universal | per-material **grace window**; binary `is_late` | `ml/labeling.py` |
| 2 | **Leakage** — future leaks into past | **causal** features: only deliveries *completed before this one was ordered* | `ml/features.py` |
| 3 | **Cold start** — new supplier, no history | 3-level **shrinkage** supplier → material×route → global; weather = seasonal normal | `ml/features.py` |
| 1 | **Small data** — overfit & fake accuracy | regularized model, few features, **k-fold CV + CIs** vs the **baseline** | `ml/train.py` |

Three ideas worth keeping:

1. **Causality is a boundary.** A row's features depend only on its past, so plain
   k-fold CV is already leakage-free. `run.py` prints the leaky-vs-causal gap so
   you can see the fantasy accuracy you'd otherwise ship.
2. **Cold start is smoothing, not a special case.** `rate = (late + k·fallback)/(n + k)`
   — with no history it *equals* the material×route fallback; it never returns NaN.
   This same math is frozen into the model artifact so `/predict` is stateless
   (see [ROADMAP.md](ROADMAP.md) "Key design decision").
3. **Weather must be honest at prediction time.** Forecasts are reliable ~10 days
   out; lead times reach 45 — so the live feature is the **seasonal normal**.

> **Note on leakage in the schema:** `suppliers.avg_delay_days` / `on_time_rate`
> are display-only rollups. They are deliberately **not** model features — the ML
> layer recomputes supplier rates causally to avoid leaking the future.

---

## Plugging in real BI Group data

- **Deliveries:** drop a CSV in the canonical schema (see `sample_deliveries.csv`)
  and point the paths at it: `python3 -m db.seed your.csv` and
  `load_training_frame(csv_path="your.csv")` / `fit_and_save(csv_path="your.csv")`.
  `ml/ingest.py` validates columns, parses dates, and drops bad rows — check a
  file first with `python3 -m ml.ingest your.csv`. Required columns (rename
  `route → route_type`): `supplier_id, material_type, route_type, quantity,
  order_date, promised_date, actual_date` (+ optional `project_site`).
- **Postgres:** set `DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db`.
- **Retrain cadence:** rerun `python3 -m ml.train` (weekly, or after each
  project's data lands). It refreshes the model and the feature snapshot together.

## Tuning knobs (business inputs, not code problems)

- **Grace-day table** — `ml/labeling.py::DEFAULT_GRACE_DAYS`. The single most
  important business input; set it with the site teams.
- **`k_shrink`** — higher = more conservative toward fallbacks when history is thin.
- **Model** — `ml/train.py::make_model()` has a one-line LightGBM/XGBoost swap.

> The synthetic late-rate (~55%) is a property of the simulator, not a forecast.
> The **methodology** — causal features, baseline, CIs, explainability — is the
> deliverable; swap in real data before reading into any absolute number.
