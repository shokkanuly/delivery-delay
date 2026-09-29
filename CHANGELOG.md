# Engineering Changelog & Internal Build Notes

This document contains internal development logs, hackathon milestones, UI refactoring history, and technical work records. All pitch- and investor-facing files (`README.md`, `docs/`, `static/index.html`, `dashboard/app.py`) remain clean and production-oriented.

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
