# Product Requirements Document (PRD)
## Construction Logistics Platform (SitePulse)

**Document Version:** 1.2.0  
**Status:** Approved / Enterprise Pilot Specification  
**Target Organization:** Regional construction holdings (first pilot target: BI Group — not yet signed)  
**Core System:** 3-Engine Integrated Construction Logistics Platform  

---

## 1. Executive Summary & Problem Context

In large-scale Central Asian construction (e.g. multi-hectare high-rise developments across Astana, Almaty, Karaganda, and Shymkent — modeled in this specification via regional pilot sites `PRJ_001` through `PRJ_005`), logistics friction represents a premier driver of margin erosion:

1. **Unpredictable Supplier Delays:** Traditional delivery tracking relies on subjective supplier promises. When a delivery of structural rebar or ready-mix concrete slips by 5–10 days, sequential trades (formwork, rebar tying, concrete pours) stall, while specialized crews and rented heavy machinery sit idle.
2. **Heavy Machinery & Gate Bottlenecks:** On dense urban sites, tower cranes, material hoists, and delivery unload bays are scarce, non-substitutable resources. Overlapping delivery arrivals create multi-hour truck queues on city streets and severe site congestion.
3. **Sequencing & Staging Congestion:** Materials delivered prematurely (e.g., facade panels arriving before the structural frame is completed) occupy critical laydown areas, suffer weather degradation in harsh climates (temperatures from -35°C in Astana to +40°C in Shymkent), and incur unnecessary double-handling costs.

The **SitePulse Platform** unifies three predictive and operational engines behind a single microservice and command surface to systematically solve these three failure modes.

> **Validation Status:** Evaluated on a 100% Synthetic Benchmark ($n=2,200$). Algorithmic guarantees (conflict-free crane scheduling, phase-gate hierarchy) are true by construction. Statistical risk and savings estimates will be calibrated against client ERP/1C logs during the 8-week pilot engagement ([`PILOT_PROPOSAL.md`](PILOT_PROPOSAL.md)).

---

## 2. User Personas & Core Use Cases

### Persona 1: Site Logistics Manager (*Kuanysh*)
* **Role:** Manages day-to-day deliveries, gate access, tower cranes, and laydown areas on site.
* **Pain Points:** Surprised by unexpected delivery arrivals, daily conflicts over crane time, yard choked with early materials.
* **User Stories:**
  * *As a Site Logistics Manager*, I want an automated daily schedule for shared equipment so that crane bookings never overlap.
  * *As a Site Logistics Manager*, I want flags for premature deliveries before trucks depart the factory so I can ask suppliers to hold shipment until the site phase is ready.

### Persona 2: Chief Procurement Officer (*Aida*)
* **Role:** Oversees contracts, supplier evaluations, and material lead times across all projects.
* **Pain Points:** Suppliers misrepresent their on-time reliability; naive vendor averages hide route- and material-specific delivery failures.
* **User Stories:**
  * *As a Procurement Officer*, I want objective, shrinkage-adjusted supplier delay risk predictions so that I can demand buffer times or switch suppliers before signing contracts.
  * *As a Procurement Officer*, I want an evidence loop showing predicted risk vs. actual historical outcomes to audit our predictive accuracy.

### Persona 3: Project Director (*Marat*)
* **Role:** Accountable for project milestone delivery, budget adherence, and contractor coordination.
* **Pain Points:** Fragmented software systems (spreadsheets, ERP, informal WhatsApp groups) that obscure critical cross-trade logistics dependencies.
* **User Stories:**
  * *As a Project Director*, I want a unified site overview showing delivery delay risk, equipment utilization, and sequencing violations side-by-side in one executive screen.

---

## 3. Product Architecture: The 3 Core Engines

```
┌────────────────────────────────────────────────────────────────────────┐
│                        SITEPULSE PLATFORM                              │
│             FastAPI Backend · Streamlit Analytics · Web Console        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
       ┌────────────────────────────┼────────────────────────────┐
       ▼                            ▼                            ▼
┌──────────────┐             ┌──────────────┐             ┌──────────────┐
│   ENGINE 1   │             │   ENGINE 2   │             │   ENGINE 3   │
│ Delay Risk   │             │   Resource   │             │   Sequence   │
│  Predictor   │             │  Scheduler   │             │  Validator   │
│              │             │              │             │              │
│ Gradient     │             │ OR-Tools     │             │ Topological  │
│ Boosting +   │             │ CP-SAT       │             │ Rules +      │
│ Shrinkage    │             │ AddNoOverlap │             │ IsoForest    │
└──────────────┘             └──────────────┘             └──────────────┘
```

### Engine 1: Delay Risk Predictor
* **Objective:** Predict probability ($0.0 - 1.0$) of a delivery exceeding its material-specific grace period.
* **Business Invariant:** Strictly causal feature construction. No leaky future statistics. Cold-start shrinkage ensures brand-new suppliers default gracefully to material-route priors without `NaN` or unhandled exceptions.
* **Output:** Risk probability, risk band (`green` < 0.35, `yellow` 0.35–0.60, `red` > 0.60), expected delay days, and top 3 interpretable risk drivers (via occlusion pass).

### Engine 2: Constraint-Based Resource Scheduler
* **Objective:** Allocate scarce heavy machinery (Tower Cranes, Concrete Pumps, Hoists, Loading Bays) to project booking requests without overlapping intervals.
* **Algorithm:** Google OR-Tools CP-SAT with `AddNoOverlap` and interval variables.
* **Risk Coupling:** Automatically ingests Engine 1 delivery delay risks to prioritize local resources and buffer high-risk slots.
* **Performance:** Solves 250+ booking requests across multi-week horizons in <0.5 seconds; no unit is ever double-booked (a tested correctness invariant).
* **Scope limit:** assigns fixed-time bookings to units across sites; it does not re-time bookings on a single fixed tower crane (next scheduler stage).

### Engine 3: Construction Sequencing Validator
* **Objective:** Ensure delivery schedule respects physical construction logic and phase readiness.
* **Rule 1 (`premature_delivery`):** Flags material arriving before target phase start date ($T_{\text{delivery}} < T_{\text{phase\_start}}$).
* **Rule 2 (`material_phase_mismatch`):** Verifies material conforms to the allowed structural material set for the designated phase.
* **Secondary Anomaly Layer:** Unsupervised Isolation Forest detects multivariate volume/timing anomalies without diluting deterministic rule precision.

---

## 4. Functional Requirements

| ID | Requirement | Priority | Target Engine / Layer | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- |
| **FR-01** | Single Delivery Scoring | Must Have | API / Engine 1 | `POST /predict` returns risk, band, and drivers in <50ms. |
| **FR-02** | Bulk CSV Batch Scoring | Must Have | API / Engine 1 | `POST /predict/batch` parses arbitrary valid CSVs and returns ranked risk list. |
| **FR-03** | Conflict-Free Scheduling | Must Have | Engine 2 | `POST /schedule` guarantees 0 overlapping bookings on shared physical equipment. |
| **FR-04** | Delay-Aware Scheduling | Should Have | Engine 2 | Solver incorporates upstream supplier risk from Engine 1 into scheduling weights. |
| **FR-05** | Build Phase Sequencing | Must Have | Engine 3 | Flags every delivery dated before its phase kickoff (deterministic rule; verified against the phase schedule). |
| **FR-06** | Project Overview Dashboard | Must Have | UI / API | `GET /projects/{id}/overview` returns unified tri-engine status for site leadership. |
| **FR-07** | Closed-Loop Outcome Logging | Must Have | Monitoring / DB | Served predictions logged; `POST /outcomes` records ground-truth actuals to compute empirical accuracy. |

---

## 5. Non-Functional Requirements

* **Latency:** Single-row inference response time $\le 50\text{ms}$ at 95th percentile.
* **Reliability:** Graceful handling of cold-start suppliers, missing weather normals, and disconnected external services.
* **Data Integrity:** Strict causal ordering in feature computation; automated tests must fail if future data leakage is reintroduced.
* **Security & Deployment:** Zero-touch dockerized execution (`docker compose up --build`), isolated network layers, and standard CORS policies.

---

## 6. Success Metrics & Key Results (OKRs)

1. **Model Lift:** Model PR-AUC exceeds supplier baseline late rate with statistical significance (95% CI > 0).
2. **Scheduling Conflict Elimination:** 100% resolution of overlapping resource conflicts (0 double-bookings after solve).
3. **Sequencing Correctness:** every delivery dated before its phase start is flagged (a correctness test, not a performance claim).
4. **Site Cost Avoidance:** measured in the pilot against the base-case estimate in [`business/economics.py`](../business/economics.py).
