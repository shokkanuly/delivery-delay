# ADR 0001: Stateless Prediction via Frozen Feature Snapshot

## Context & Problem Statement
Delay prediction in construction logistics relies heavily on supplier historical performance (historical late rate, order counts, route difficulty). In a traditional database-backed architecture, scoring a new delivery requires querying the database for all past deliveries by that supplier up to the order date and computing rolling aggregations on the fly.

This approach creates severe issues:
1. **Latency:** Per-request historical window aggregations introduce multi-second latency and heavy SQL load.
2. **Data Leakage Risk:** Running ad-hoc SQL queries easily introduces subtle lookahead bias (e.g. querying up to `today` instead of the delivery's `order_date`).
3. **Availability Dependency:** Inference becomes tightly coupled to high-availability database read replicas.

## Decision
We freeze causal historical statistics into a serialized artifact (`model.joblib`) at training time:
- Causal supplier historical late rates and sample counts
- Material × route cross-tabulated prior late rates
- Empirical feature medians for imputation and occlusion explainability

During online scoring (`POST /predict`):
- The model inspects the frozen snapshot in memory (O(1) dictionary lookup).
- If a supplier is unknown (cold start), empirical Bayes shrinkage smoothly blends into the material × route prior without database round-trips.
- Scoring is completely stateless, idempotent, and completes in <15ms.

## Consequences & Trade-offs
### Positive
- **Predictable Latency:** Inference completes in single-digit milliseconds.
- **Zero Online DB Dependencies for Scoring:** The prediction engine can score even if the database is in maintenance.
- **Auditable Reproducibility:** Every prediction is tied to an explicit `model_version` and frozen feature state.

### Negative / Mitigations
- **Snapshot Staleness:** Historical rates do not update until the next model retraining.
- *Mitigation:* The platform exposes a synchronous `POST /train` endpoint and retraining pipeline that regenerates the artifact when new batches of delivery actuals arrive.
