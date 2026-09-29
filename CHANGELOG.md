# Engineering Changelog & Internal Build Notes

This document contains internal development logs, hackathon milestones, UI refactoring history, and technical work records. All pitch- and investor-facing files (`README.md`, `docs/`, `static/index.html`, `dashboard/app.py`) remain clean and production-oriented.

---

## [1.3.0] — 2026-09-29 · Pitch Credibility, Single Source of Economics, Design System

Driven by an honest jury-rubric review; plan and rationale in `docs/plans/credibility-fixes.md`.

### Added
- `business/economics.py` — every pitch number (per-site ROI in conservative/base/upside scenarios, unit economics, the one 3-year forecast, bottom-up market) computed from assumptions tagged by source. Served at `GET /economics`; `POST /economics/site` for live what-if editing.
- `tests/test_pitch_claims.py` — fails if README/docs/UIs reintroduce retired claims or if the deck quotes a figure `business/economics.py` does not produce.
- `tests/test_workspace_contract.py`, `tests/test_economics.py`, `tests/test_design_system.py`.
- `DESIGN.md` + `static/design/` (tokens.css with light/dark themes, SitePulse SVG mark/wordmark, icon) shared by both UIs; five-badge claim vocabulary.
- `docs/CUSTDEV_LOG.md` — interview evidence template the deck's problem slide must trace to.

### Fixed
- Company workspace save returned HTTP 422 from both UIs (field names did not match `CompanyWorkspaceIn`) and the form never loaded (response envelope ignored). Finance is now computed on read, never stored.
- Three different ROI formulas (API, dashboard, console) replaced by one.
- Console inputs referenced an undefined `--bg-primary`; dashboard badges were recoloured by a global markdown rule; `$\rightarrow$` rendered as a carriage return.

### Changed
- Retired claims: "piloting with BI Group" (no signed pilot), "BI SITE-PULSE" branding, "LightGBM" (model is scikit-learn HistGradientBoosting), "100% recall" (tautological on rule-generated labels), $621k / 221.8% / >14× ROI, 19.4:1 LTV:CAC, 140% NRR, "83%" of 7 interviews, and the self-graded rubric table.
- Scheduler described as what it does — cross-site equipment dispatch of fixed-time bookings — not single-tower-crane hook-time re-timing.
- Competition section names Voyage Control, ALICE Technologies, nPlan, Procore/Fieldwire; moat stated honestly.
- Fonts Inter/Instrument Serif/JetBrains Mono → Geist/Geist Mono; emojis removed from UI copy.
- Design system applied in full (DESIGN.md rewritten in the Stitch 7-section format): console is responsive below 768px (single column, 2-column nav, 44px targets, zero horizontal overflow at 390px); `100vh` → `100dvh`; shadows tinted Zinc instead of black; feature rows asymmetric (engines 1.3/1/1, pricing and market lead the middle); cascade reveals, skeleton shimmer and 1px press feedback, all disabled under `prefers-reduced-motion`.
- Remaining tautological wording retired ("100% detection", "Validation Accuracy 100%", "100% coverage").

---

## [1.2.0] — 2026-09-28 · Credibility, Provenance & Partner Positioning Upgrade

### Added
- **Data Provenance Labeling**:
  - Labeled all reported metrics as either `100% Synthetic Benchmark (n=2,200 deliveries, 260 crane bookings)`, `Real Historical Data (0% connected in MVP)`, or `Mix`.
  - Reported evaluation set class balance / base rate (`40.9% late deliveries`, 899/2,200 late) alongside PR-AUC (`0.858`) and ROC-AUC (`0.831`), providing essential context for PR-AUC interpretation against naive random guessing (`0.409`) and supplier-average baseline (`0.732`).
- **Claim Categorization**:
  - Distinct badge badges: `[Algorithmic Guarantee]` (Cyan `#0284C7`) for CP-SAT's zero double-bookings and phase-gate validator's 100% recall (mathematically guaranteed by construction).
  - `[Statistical Estimate · Synthetic Benchmark]` (Amber `#D97706`) for LightGBM delay risk, dollar savings ($621k/site), concrete spoilage protection, and projected ROI range (221.8%).
- **Validation Status Framework**:
  - Added dedicated Validation Status sections across `README.md`, `docs/ARCHITECTURE.md`, `docs/PRD.md`, and top-level banners and footers in Streamlit and the HTML console.
  - Specified the concrete calibration next step: ingesting 6–12 months of ERP/1C dispatch logs and crane telematics via `ml/ingest.py`.
- **Pilot & Procurement Specifications**:
  - Created `docs/PILOT_PROPOSAL.md` and added integrated "Pilot Engagement" tabs in `dashboard/app.py` and `static/index.html`.
  - Defined 6–8 week dual-site pilot engagement phases, required client data schema, production timeline, and SaaS pricing ($15k pilot fee; $3,500–$4,500/site/month).

### Changed
- **Positioning Alignment**:
  - Standardized positioning: *Enterprise Construction Logistics Platform — Designed for Regional Construction Holdings (Piloting with BI Group)*, eliminating vague hedges ("such as BI Group").
  - Replaced unapproved project names and access keys with clear fictional placeholders: `Site A · Urban Residential (Almaty)`, `Site B · High-Rise Commercial (Astana)`, `Site C · Embankment Towers (Astana)`, `Site D · Industrial Logistics Park (Karaganda)`, `Site E · Regional Trade Center (Shymkent)`.
  - Updated access keys: `DEMO-SITE-B-2026`, `DEMO-SITE-A-2026`, `DEMO-PILOT-KEY`.

---

## [1.1.0] — 2026-09-27 · Enterprise UI Modernization & Project Workspace

### Changed
- Complete visual overhaul of Streamlit dashboard (`dashboard/app.py`) and Web Console (`static/index.html`):
  - Stripped all informal sticker-style emojis in favor of crisp mathematical and geometric symbols (`⊘`, `⊞`, `⬡`, `⚡`, `↗`, `↘`).
  - Implemented cohesive dark industrial palette: Dark Slate background (`#0B0F17`), Navy cards (`#161D2B`), Safety Orange accent (`#FF5E36`), Industrial Green (`#10B981`), Warning Amber (`#F59E0B`).
  - Added typography stack: Inter, JetBrains Mono, and Instrument Serif.
- Added **Project Workspace & Financial Configurator**:
  - Configurable parameters: site area, floors, tower crane count, daily equipment lease rate, and concrete volume.
  - Dynamic mathematical formulas calculating machinery run cost, crane standstill savings, concrete spoilage protection, and project ROI.
  - Key-based workspace state persistence (`data/workspaces.json`).

---

## [1.0.0] — 2026-09-26 · 3-Engine Platform Integration

### Added
- **Engine 1 (Delay Risk Predictor)**: LightGBM / HistGradientBoosting with causal empirical-Bayes shrinkage and occlusion-based risk drivers.
- **Engine 2 (Resource Conflict Resolver)**: Google OR-Tools CP-SAT constraint programming solver enforcing `AddNoOverlap` for tower crane and unload bay scheduling.
- **Engine 3 (Sequence Validator)**: Phase-gate rule validator catching premature delivery staging with 100% recall.
- Unified REST API in FastAPI (`api/main.py`) exposing `/predict`, `/schedule`, `/validate`, and `/projects/{id}/overview`.
- Synthetic Kazakhstan logistics corridor dataset generation (`data/synthetic/`).
