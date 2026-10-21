# SitePulse — current product scope

Working prototype; one construction site. [Research](RESEARCH.md) · [Roadmap](../ROADMAP.md) ·
[Implementation plan](plans/mvp-reshape.md).

## User and first decision

The procurement lead/site manager imports a 1C delivery history, checks its quality and reviews
supplier reliability by material. A useful first output is a defensible supplier scorecard.
The director is the prospective buyer. These roles and the daily workflow need interview validation.

## Implemented acceptance criteria

| Requirement | Contract / verification |
|---|---|
| Import 1C CSV | UTF-8/cp1251; known Russian aliases; invalid quantities, dates, duplicates and defaults reported. |
| Supplier history | Shared lateness rules; counts, Wilson 95% interval, late-only quantiles and shared 90-day trend. |
| Backtest | Chronological 70/30; tied order dates stay together; outcomes unresolved at cutoff are purged. Minimum 50 train/20 test rows and both classes. |
| Baseline comparison | Supplier-average baseline on the same holdout; no risk-band report unless the model wins. |
| Authenticated upload | POST /audit/history; admin key; 5 MB / 10,000 rows; no archival by default. |
| Public example | Saved synthetic report from the same domain code and downloadable CSV. No credentials and no arbitrary upload endpoint. |
| Tenge exposure | All five inputs required; known answer 350,000 ₸; never labelled measured savings. |
| Equipment solver | No overlapping assignment per physical unit; fixed requested times, not a full approval workflow. |
| Arrival evidence | Signed idempotent gate events, unmatched review and prediction/outcome logs. |

## Planned, not implied by a screenshot

Migrations, named roles, request/approve/reject/move states, supplier booking links, a daily at-risk
view, outbound notifications, customer production hosting and backup/restore verification.
Multi-site and multi-tenant operations follow customer evidence, not competition slide pressure.

## Data and operational boundaries

Public Railway: synthetic demonstration only. Each real pilot gets a separate Kazakhstan/on-prem
stack. Approve data handling and retention before intake. No automatic promotion of uploaded
history to the serving model. The static console is the product; Streamlit is an internal analyst
surface. No latency, availability or customer-effect SLA is established by synthetic tests.
