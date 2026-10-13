# Plan — Pitch credibility fixes (LaunchZone 2026)

Status: `[ ]` todo · `[~]` in progress · `[x]` done.

## Why

An honest jury review (see the evaluation in the session that produced this
plan) scored the project ~43–47/100 today. The points are lost on claims,
not code: numbers that contradict each other across files, labels the code
does not back ("LightGBM", "piloting with BI Group"), and headline metrics
that are tautological. Goal: every number a juror can see comes from one
place, and every claim is one the repo can defend.

## What exists (the territory)

- Pitch numbers are hardcoded in ~8 files (README, 5 docs, Streamlit
  dashboard, HTML console).
- The per-site ROI formula exists **three times with three definitions**:
  `api/main.py::compute_workspace_finance` (ROI vs 8% of logistics budget →
  221.8%), `dashboard/app.py` (vs 0.8% of project budget), and
  `static/index.html::calculateCompanyKPIs` (same as dashboard, in JS). The
  deck's ">14×" is a fourth (value / licence fee).
- **Contract bug at the UI ↔ API boundary:** both UIs POST workspace fields
  (`tower_cranes_count`, `crane_daily_rate_usd`, …) that do not exist in
  `CompanyWorkspaceIn` (`cranes_count`, `crane_daily_rate`, …, required
  `project_id`) → HTTP 422 on every save. Both UIs also read fields at the top
  level of a `{found, workspace}` envelope → the form never loads. No test
  covers `/projects/workspace`.
- `data/workspaces.json` persists *derived* finance, so a formula change
  never reaches saved workspaces.

## Design

Chosen: **one pure module `business/economics.py`** holding every business
assumption (with its provenance) and every derived figure — per-site ROI
scenarios, unit economics, the single forecast, market sizing. The API serves
it (`GET /economics`, and workspace finance computed at read time); both UIs
render what the API returns instead of recomputing; a test asserts that the
figures quoted in README/deck equal the module's output, so drift fails CI.

Rejected: a hand-maintained `ASSUMPTIONS.md` (the current drift *is* the
hand-maintenance failure mode); generating docs from templates (new tooling,
more than the problem needs).

Deviation noted: `business/` is a new top-level package. It follows the
`ml/` pattern (pure functions, no web imports) and exists because economics
is neither an engine nor API glue.

## Roadmap

### Stage 1 — Economics single source of truth `[x]`
- **Goal:** one module computes every pitch number from explicit assumptions.
- **Steps:** `business/economics.py` (assumptions with provenance; site ROI
  in conservative/base/upside; unit economics with margin-adjusted LTV, no
  NRR; one 3-year forecast; bottom-up market; break-even month derived);
  `GET /economics` in `api/main.py`; `tests/test_economics.py`.
- **Depends on:** nothing.
- **Done when:** `pytest tests/test_economics.py` passes and
  `GET /economics` returns the same figures.

### Stage 2 — Fix the workspace contract `[x]`
- **Goal:** saving/loading a workspace works from both UIs; finance comes from
  Stage 1.
- **Steps:** API computes finance at read time via `business.economics`;
  stop persisting derived finance; both UIs send `CompanyWorkspaceIn` field
  names, unwrap `workspace`, and render API finance instead of local math.
- **Depends on:** Stage 1.
- **Done when:** a round-trip test (POST schema-shaped payload → GET) passes,
  and the UI payload shapes match the schema.

### Stage 3 — Claims hygiene in docs `[x]`
- **Goal:** docs say only what the repo can defend, with numbers from Stage 1.
- **Steps:** README, INVESTOR_DECK (delete self-score table; one forecast;
  scheduler pitched as equipment dispatch, which is what the code does; named
  competitors; interview claims as raw counts / placeholders; honest Q&A),
  PILOT_PROPOSAL, PRD, ARCHITECTURE, CONTRIBUTING, RUNBOOK, ROADMAP, code
  comments. "LightGBM" → gradient boosting; "piloting with BI Group" → target
  pilot partner; guarantees reframed as correctness invariants.
- **Depends on:** Stage 1.
- **Done when:** `tests/test_pitch_claims.py` passes (banned phrases absent;
  quoted figures equal `business.economics` output).

### Stage 4 — Claims hygiene in the UIs `[x]`
- **Goal:** dashboard and console show the same honest claims and numbers.
- **Steps:** replace hardcoded investor numbers in `dashboard/app.py` with
  `GET /economics`; fix labels in both UIs; drop partner brand from product
  title ("BI SITE-PULSE").
- **Depends on:** Stages 1–2.
- **Done when:** the banned-phrase test also covers both UI files and passes;
  the dashboard renders against a live API.

### Stage 5 — Design system `[x]`
- **Goal:** both UIs share one documented token set and one claim-badge
  vocabulary (guarantee / estimate / assumption).
- **Steps:** `DESIGN.md`; shared tokens file used by both UIs.
- **Depends on:** Stage 4.
- **Done when:** both UIs load the same tokens; screenshot check of both.

## Mid-build discoveries
- `data/workspaces.json` carried a `BI-ALATAU-2026` key (partner prefix, duplicate
  of Site B) — removed.
- The raster logos (`static/logo*.png`, `dashboard/assets/logo*.png`) contain
  "BI SITE-PULSE" in the artwork. Both UIs now use `static/design/mark.svg`; the
  PNGs are unreferenced and left for the founder to delete.
- `.greeting` used a serif; dashboard badges were being recoloured by a global
  `.stMarkdown span` rule; one engine description rendered `$\rightarrow$` as a
  carriage return. All fixed in Stage 5.
- ~200 inline hex colours were mapped onto tokens; the only colour duplicate left
  is `.streamlit/config.toml` (TOML cannot read CSS variables), guarded by a test.

## Founder inputs still needed (cannot be derived from the repo)
- Raw interview counts behind the problem-slide claims.
- Whether any written pilot commitment / LOI exists.
- Real local cost inputs (crane day rate, concrete price, LD penalty) to
  replace the defaults in `business/economics.py`.
- A named advisor, or remove the advisor line.
