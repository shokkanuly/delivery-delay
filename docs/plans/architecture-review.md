# Architecture Review — SitePulse (2026-09-29)

Status: `[ ]` todo · `[~]` in progress · `[x]` done. **All stages done (go-ahead given 2026-09-29).**

## 1. Why (scope and success)

- **Problem:** find the structural weaknesses a technical juror or a first pilot
  customer would hit, now that the pitch claims are honest.
- **Users:** the founder (demoing locally or via Docker), a pilot holding's IT and
  logistics staff (real data, several companies), and jurors reading the repo.
- **Constraints:** a solo founder; the pitch is days away; the current stack
  (FastAPI, SQLAlchemy, scikit-learn, OR-Tools, Streamlit, static HTML) stays; the
  118 tests must stay green.
- **Success:** the demo shows the model the README describes; no endpoint claims
  security it does not have; one store of record; every fix is covered by a test.

## 2. The territory (what exists)

**Conventions to keep**
- Pure, framework-free domain modules: `ml/`, `engines/scheduler`,
  `engines/validator`, `business/`. They take DataFrames/dicts and return data.
- The API is organised by domain in `api/routers/<domain>.py` (schedule,
  validate, monitoring). Reference data is read DB-first with a CSV fallback
  (`api/data_sources.read_reference`). SQLAlchemy models in `db/models.py` are
  the single schema; SQLite ↔ Postgres is chosen via `DATABASE_URL`.
- Tests run against a temp SQLite DB and a small temp-trained model
  (`tests/conftest.py`), and pin invariants rather than exact numbers.

**Where the pattern is broken:** `api/main.py` also holds workspace
persistence, economics, overview composition and predict routes. The
`/economics` endpoints added in the credibility pass followed the workspace
code's location, not the router pattern; that deviation is tracked below.

## 3. Findings (most severe first)

| # | Severity | Boundary | Finding | Evidence |
|---|---|---|---|---|
| F1 | **High** | App ↔ ML | On the local path, the served model recognises **none** of the suppliers it scores. `start.sh` and the README quickstart run `ml.train` with no argument, which trains on `ml/data_sim` (suppliers `S00`–`S24`, 1,200 rows). The DB is seeded from `data/synthetic/delay_prediction.csv` (suppliers `SUP_001`–`SUP_010`, 2,200 rows). **0 of 10** scored suppliers are known, so every dashboard score is a cold-start fallback, and `/health` reports 1,200 training rows while the README's metrics describe 2,200. Docker and Render pass the CSV and are correct. The artifact does not record its data source, so nothing detects the mismatch. | Checked by loading `ml/artifacts/model.joblib` and intersecting its supplier snapshot with each CSV. |
| F2 | **High** | Client ↔ server | **No authentication anywhere**, while the UIs say "Key-Secured Workspace", "Authorized Contractor Portal" and "ML Internal Access: Restricted", and the pilot proposal promises a "Security & Tenancy Guarantee". Anyone who can reach the API can overwrite any workspace by key (the demo keys are printed in the README), trigger a synchronous CPU-heavy retrain (`POST /train`), or poison the evidence log (`POST /outcomes`). CORS pairs `allow_origins=["*"]` with `allow_credentials=True`. | `api/main.py:48-49`, `/train`, `api/routers/monitoring.py:66` |
| F3 | Medium | App ↔ data | **Two stores of record.** Workspaces live in `data/workspaces.json`, a file tracked in git and rewritten at runtime, even by a `GET` for an unknown demo key. It is not on a Docker volume, so saves are lost on restart; concurrent saves race; and running the app dirties the git tree (it happened twice in this session). | `api/main.py::_save_workspaces`, `get_company_workspace` |
| F4 | Medium | UI ↔ UI | **Two UIs implement the same eight views**: Streamlit (~2,000 lines) and the HTML console (~3,000 lines). Every fix in the credibility pass had to be made twice (the workspace contract, the claims, the tokens). This is a duplicated-type problem at product scale. | `dashboard/app.py`, `static/index.html` |
| F5 | Medium | API structure | `api/main.py` mixes app wiring with four domains, while the rest of the API uses routers. It includes the `/economics` routes this project's own credibility pass added (a deviation). | `api/main.py` |
| F6 | Low | Client ↔ server | Console fallbacks `\|\| 260`, `\|\| 99`, `\|\| 219`, `\|\| 27` show made-up numbers when the API fails, and would show 27 instead of a real 0 (Site B has 0 premature deliveries and 0 conflicts). | `static/index.html:3008-3046` |
| F7 | Low | Credibility | Static demo content is presented as live: a "Good morning, Aidos" persona, "Tuesday, 12 March 2025 · 07:30", and weather "−6° / +2°, wind 18 km/h". Compose names Postgres `bigroup`/`deliverydb`, a partner brand in infra config. | `static/index.html:1472,1486`, `docker-compose.yml` |

## 4. Design options

- **A. Fix in place, most severe first (recommended).** Each finding becomes a
  small stage with its own test; the demo gets more trustworthy after every
  stage, and nothing waits on a product decision. Cost: F4 stays duplicated until
  the last stage, so stages 2 and 6 touch both UIs.
- **B. Consolidate the UIs first, then fix once.** Fewer edits in total, but it
  blocks the two High findings behind a large product decision days before the
  pitch.
- **C. Fix only the bugs (F1, F6) and document the rest.** Cheapest, but it
  leaves F2: a pilot with real client data cannot start on an API without any
  access control.

**Chosen: A**, because the High findings are cheap and independent, and F4 needs
the founder's call anyway. No new libraries: auth uses FastAPI's built-in
`APIKeyHeader`, and workspaces use the existing SQLAlchemy session.

## 5. Roadmap

### Stage 1 — One training source, detectable drift (F1) `[x]`
- **Goal:** every run path trains on the data the DB is seeded from, and a
  mismatch becomes visible.
- **Steps:**
  - `ml/train.py`: the default `csv_path` becomes `data/synthetic/delay_prediction.csv`,
    which is `db.seed`'s default; `ml/data_sim` stays for tests only.
  - Record `data_source` and the supplier count in the artifact.
  - `/health` reports `supplier_coverage` (DB suppliers known to the model).
  - Align `start.sh` and the README quickstart.
- **Depends on:** nothing.
- **Done when:** a fresh `start.sh` run shows `/health` → `trained_rows: 2200`,
  `supplier_coverage: 1.0`; a new test fails if the seed and train defaults diverge.

### Stage 2 — No invented numbers (F6) `[x]`
- **Goal:** the console shows a real 0 as 0, and an inline error on API failure.
- **Steps:** `static/index.html`: `||` → `??`; failure shows "—" plus an inline
  error (DESIGN.md §4).
- **Depends on:** nothing.
- **Done when:** a test finds no `|| <number>` fallbacks; the Site B sequence
  view shows 0 in the browser.

### Stage 3 — Workspaces in the database (F3) `[x]`
- **Goal:** one store of record; `GET` has no side effects.
- **Steps:**
  - Add a `Workspace` model in `db/models.py` and seed the demo workspaces in `db/seed.py`.
  - The API reads and writes through `get_session`; delete `data/workspaces.json`.
  - A `GET` for an unknown key returns 404.
- **Depends on:** nothing (Stage 5 moves the routes afterwards).
- **Done when:** the workspace contract tests pass against the temp DB; running
  the app and saving a workspace leaves `git status` clean; a test proves `GET`
  writes nothing.

### Stage 4 — Access control that matches the UI's words (F2) `[x]`
- **Goal:** mutating endpoints are protected, and the UI claims only what is true.
- **Steps:**
  - An `X-API-Key` header (env `SITEPULSE_ADMIN_KEY`) on `POST /train` and
    `/outcomes`. Streamlit holds the key server-side; the browser never sees it.
  - New workspace keys become random 128-bit tokens; demo workspaces are read-only.
  - CORS origins come from env, not `*` with credentials.
  - Reword "Key-Secured / Authorized / Restricted" to what is actually enforced.
- **Depends on:** Stage 3.
- **Done when:** tests show 401 without the key and 200 with it; a demo workspace
  rejects writes; `tests/test_pitch_claims.py` bans the unbacked security wording.

### Stage 5 — Routers for every domain (F5) `[x]`
- **Goal:** `api/main.py` does wiring only, matching the existing router pattern.
- **Steps:** `api/routers/business.py` (economics, workspace),
  `api/routers/predict.py`, `api/routers/projects.py` (overview). A pure move.
- **Depends on:** Stages 3–4 (so their code moves once).
- **Done when:** the full suite passes unchanged, and the path list in
  `/openapi.json` is identical before and after.

### Stage 6 — Honest demo content (F7) `[x]`
- **Goal:** nothing static pretends to be live.
- **Steps:** the date comes from the browser clock; a neutral "Demo user" replaces
  the persona; the weather widget gets a "sample" label or is removed; rename the
  compose DB user/name.
- **Depends on:** nothing.
- **Done when:** a grep test bans the persona and the fixed date; the compose
  stack comes up healthy.

### Stage 7 — Decide the one UI (F4) `[x]` · *founder decision*
- **Goal:** one maintained surface.
- **Recommendation:** keep the **HTML console**. It is served by the API itself
  (one process, one URL, one deploy), it is now mobile-responsive, and it has no
  Streamlit rerun limits. Keep Streamlit only as an internal analyst tool, or
  delete it.
- **Depends on:** founder decision; best after the pitch.
- **Done when:** the decision is recorded here and the dropped UI is removed or
  marked internal in the README.

## 6. Outcome and mid-build notes

- **Stage 1.** Verified on a fresh `start.sh` run: `/health` returns
  `trained_rows: 2200`, `data_source: delay_prediction.csv`, `supplier_coverage: 1.0`
  (it was 0.0). `tests/test_training_source.py` pins the shared default.
- **Stage 2.** Skeletons replace the hardcoded initial KPI values too (260, 99,
  "OPTIMAL (0.2s)", 219, 27), not only the `||` fallbacks.
- **Stages 3 and 4 were built together** because they share the same code. The
  workspace routes were written straight into `api/routers/business.py` so
  Stage 5 did not have to move them. The demo data moved to
  `data/synthetic/demo_workspaces.json` (read-only seed input). The API now
  creates missing tables at startup (`init_db` in the lifespan).
- **Stage 4 key flow.** A blank key on save gets a server-issued `WS-…` token.
  Unknown keys return 404; demo keys return 403. The admin key is generated by
  `start.sh`, set in `.env` for compose, and uses `generateValue` on Render,
  shared with the dashboard service. Admin endpoints return 503 when no key is
  configured. CORS is an explicit list (the console is same-origin; Streamlit
  calls the API server-side).
- **Stage 5.** `api/main.py` went from ~350 lines to wiring only. New modules:
  `api/model_store.py`, `routers/predict.py`, `routers/projects.py`,
  `routers/business.py`. The 21 OpenAPI paths are identical to the pre-split
  commit (diffed via a worktree).
- **Stage 6.** The Postgres user and DB are renamed `sitepulse`. The weather
  widget is kept but labelled "Sample conditions · not live".
- **Stage 7 decision (founder: "do everything").** The HTML console is the
  product; Streamlit is an internal analyst view (README, `start.sh`, module
  docstring). Nothing was deleted, so the decision is reversible.
- **Remaining, out of scope:** Streamlit's own server runs with
  `enableCORS=false` (pre-existing, `.streamlit/config.toml`). Revisit if
  Streamlit is ever exposed publicly.
