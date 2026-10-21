# One-site pilot proposal — discussion draft

No partner, contract, price or production SLA is agreed. This proposal follows the
[research-backed scope](RESEARCH.md): a useful audit before a larger integration.

## First deliverable: a free historical audit

A procurement lead provides an authorised 1C/CSV export for one site: supplier/material IDs,
quantity, order date, promised date and actual arrival date. Agree material grace rules and
remove unnecessary personal fields before transfer. Do not upload real customer history to
public Railway. Set up the customer's Kazakhstan/on-prem environment first.

Return a quality report, supplier/material scorecards and a chronological model-versus-baseline
comparison. An insufficient-history or model-below-baseline result is an acceptable outcome.
Record whether the procurement lead can use the report to change or confirm a supplier decision.

## Proposed 30-day pilot

| Period | Proposed activity | Evidence to retain |
|---|---|---|
| Before day 1 | Agree site, data handling, operator, permitted integrations and success criteria | Written scope and baseline; no assumed savings. |
| Days 1–7 | Review historical audit and map orders to arrivals | Import quality, agreed grace periods and matching coverage. |
| Days 8–21 | Run in shadow mode with the existing dispatch process | Served predictions, actual arrivals, unmatched events and recorded decisions. |
| Days 22–30 | Review adoption, evidence gaps and commercial decision | Report accepted by site staff; continue/change/stop decision. |

Proposed targets to agree with the contractor: arrival coverage of at least 80%; staff reviewing
the report at least three days per week; live accuracy published only after at least 100 resolved
deliveries. These are pilot targets, not results already achieved.

The existing scheduler proposes fixed-time equipment assignments. Human booking approval,
role keys and outbound notifications are pending implementation. Confirm those prerequisites
before promising them in an operational pilot. The historical audit can be evaluated independently.

## Value and payment

Compute exposure in tenge from the contractor's contract value, penalty rate, delay days,
idle hours and hourly rate. Exposure is potential cost under entered assumptions, not causal
proof of losses avoided. Measure savings separately using an agreed baseline/control approach.

First historical audit: proposed free. A one-site shadow pilot may be free under agreed access
and conversion terms. The founder's 150,000–300,000 ₸ per active site/month subscription range,
and 500,000–1,000,000 ₸ eight-week paid-pilot range, are hypotheses from the supplied pitch.
Choose one concrete commercial proposal with the partner; these ranges are not a binding offer.
Suppliers would not pay to submit a booking request.

## Stop or narrow the pilot if

The export cannot support reliable matching; the site cannot assign an owner; the scorecard
does not inform a decision; or customer hosting/security prerequisites are not met. A model that
fails the baseline is not a reason to fabricate a positive result or expand the scope.
