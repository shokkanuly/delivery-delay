# Delivery-Delay MVP — Build Roadmap

Full 3-layer MVP (Data → ML → Application) for BI Group. Each stage ends with
something runnable/verifiable. Status: `[ ]` todo · `[~]` in progress · `[x]` done.

**Key design decision.** Causal features need history to score a delivery, so
prediction is not naturally stateless. The trained artifact carries a *feature
snapshot* (causal supplier / material×route / global late-rates as of training
time). `/predict` looks the supplier up in that snapshot — fast, stateless,
honest. Postgres is the store-of-record; the snapshot refreshes on retrain.

---

## Stage 0 — Restructure core into `ml/` package  `[x]`
- **Goal:** existing correctness core lives in an importable `ml/` package.
- **Steps:** add `ml/__init__.py`; move `data_sim/labeling/features/baseline/train.py`
  into `ml/`; fix imports to `ml.*`; keep `run.py` at root as the correctness demo.
- **Depends on:** nothing.
- **Done when:** `python run.py` still prints the four-problem report.

## Stage 1 — Persist model artifact + `predict.py`  `[x]`
- **Goal:** a saved model that can score a new delivery and explain why.
- **Steps:** `ml/train.py::fit_and_save()` fits on all data, stores model +
  feature snapshot + column order + label config + global importance + CV metrics
  to `ml/artifacts/model.joblib`. `ml/predict.py` loads it, scores a dict or
  DataFrame, and returns top risk drivers via occlusion (replace feature with
  train median, measure probability drop — model-agnostic, no extra deps).
- **Depends on:** Stage 0.
- **Done when:** `python -m ml.predict` prints risk + drivers for a sample delivery.

## Stage 2 — Data layer (SQLAlchemy + seed)  `[x]`
- **Goal:** deliveries/suppliers/projects/weather persisted and queryable.
- **Steps:** `db/models.py` (suppliers, deliveries, projects, weather_log);
  `db/database.py` (engine/session, SQLite default, `DATABASE_URL` for Postgres);
  `db/seed.py` loads synthetic data.
- **Depends on:** nothing (parallel to 0/1).
- **Done when:** `python -m db.seed` populates the DB and prints row counts.

## Stage 3 — API (FastAPI)  `[x]`
- **Goal:** the three plan endpoints, backed by the artifact + DB.
- **Steps:** `api/schemas.py` (Pydantic in/out); `api/main.py` with
  `GET /health`, `POST /predict`, `POST /predict/batch` (CSV upload),
  `GET /deliveries/{project_id}` (list w/ risk from DB).
- **Depends on:** Stages 1 & 2.
- **Done when:** FastAPI TestClient gets a risk score for a sample and lists
  a project's deliveries.

## Stage 4 — Dashboard (Streamlit)  `[x]`
- **Goal:** the demo UI judges will see.
- **Steps:** `dashboard/app.py` — CSV drag-drop → color-coded risk table
  (red/yellow/green), row detail with drivers, project filter. Calls the API.
- **Depends on:** Stage 3.
- **Done when:** app renders a scored table from an uploaded CSV.

## Stage 5 — Deployment  `[x]`
- **Goal:** one-command local/VM run.
- **Steps:** `Dockerfile`, `docker-compose.yml` (postgres + api + dashboard),
  `.env.example`; README run instructions.
- **Depends on:** Stages 3 & 4.
- **Done when:** `docker compose config` validates; README documents the run.

---

# Phase 2 — Construction Logistics Platform

Three engines, one FastAPI service, one dashboard, shared master data
(`data/synthetic/`). Engine 1 is the proven module; 2 and 3 are its natural
extensions.

## Stage 7 — Resource scheduler (engine 2)  `[x]`
OR-Tools CP-SAT, optional intervals + AddNoOverlap. On 260 synthetic bookings:
99 raw conflicts → 260/260 assigned, **0 double-bookings** (independently
verified from the output), OPTIMAL in ~0.2s, 19/28 resources used.

## Stage 8 — Sequence validator (engine 3)  `[x]`
R1 premature delivery + R2 material/phase mismatch. **Precision 1.0 / recall
1.0** vs the ground-truth flag column.

## Stage 9 — Unified API + platform dashboard  `[x]`
`/schedule`, `/validate` mounted alongside `/predict`; `/projects/{id}/overview`
returns all three engines for one site; dashboard "Project overview" tab.

## Stage 10 — Evidence loop  `[x]`
`prediction_log` + `/outcomes` + `/accuracy`. `scripts/evidence_loop.py` trains
on the oldest 80% and predicts the newest 20%: green 24.8% / yellow 40.4% /
red 74.5% actually ran late.

## Stage 11 — Test suite + CI  `[x]`
55 pytest tests: leakage guard, cold-start fallback, scheduler no-overlap
invariant, validator recall, ingest validation, API smoke across all three
engines, and regressions for the two seed bugs. Mutation-checked — injecting
leakage into features.py and disabling AddNoOverlap both make the suite fail.
GitHub Actions runs them on 3.11 + 3.12 and builds the Docker image.

## Stage 12 — Docker end-to-end  `[x]`
`docker compose up --build` verified: Postgres healthy, seed+train completes,
all three engines answer over HTTP, dashboard serves. Fixed the compose seed to
read the same CSV as training (it previously seeded from the old generator, so
every supplier cold-started inside the container).

## Stage 13 — Public demo URL  `[ ]`
`render.yaml` blueprint is ready. Needs a Render account: New -> Blueprint ->
pick this repo. Cannot be done without the account owner.

## Known gaps (deliberate)
- 3-class status head (`early` is 4.3% of rows — too thin to learn honestly).
- `expected_delay_days` does not beat predicting the mean; flagged in the UI.
- Recall 0.45 at threshold 0.5 — set the cutoff from real intervention costs.
- All data is synthetic; `ml/ingest.py` is the real-data seam.
