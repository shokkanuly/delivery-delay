# ADR 0003: Hybrid Deterministic & Unsupervised Construction Sequencing Validation

## Context & Problem Statement
Construction project schedules are governed by strict physical dependencies:
- Foundation concrete must be poured before structural steel erection can begin.
- Interior finishing materials must not arrive when the building envelope is still exposed to weather.

When validating delivery dates against project build phases:
- A purely black-box ML model (e.g. classification) is prone to false negatives on clear-cut physical violations and lacks explainability for site superintendents.
- A purely hardcoded rule engine cannot detect multivariate anomalies (e.g., an abnormal cluster of small shipments or out-of-distribution quantities).

## Decision
We implement a two-tier hybrid validation architecture:
1. **Tier 1 (Deterministic Business Rules):**
   - **Rule 1 (`premature_delivery`):** Hard date comparison between material arrival date and phase start date ($T_{\text{delivery}} < T_{\text{phase\_start}}$).
   - **Rule 2 (`material_phase_mismatch`):** Verifies material conforms to the allowed structural material set for the designated phase.
   - *Guarantee:* 100% recall and explainability on verified phase schedules.
2. **Tier 2 (Unsupervised Isolation Forest):**
   - Runs secondary multivariate anomaly detection on delivery quantity, lead time, and phase duration.
   - Reported as a separate score (`isolation_forest_anomaly`) so that it never dilutes the deterministic rules' precision.

## Consequences & Trade-offs
### Positive
- **Auditable Decisions:** Superintendents receive actionable, non-cryptic explanations ("Rebar arriving 12 days before Foundation phase start").
- **Exploratory Anomaly Detection:** Catches suspicious deliveries that pass hard schema checks but deviate from historical patterns.
- **Independent Evolution:** Rule definitions can be refined by field engineers without retraining the ML anomaly model.
