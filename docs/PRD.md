# SitePulse — delivery-evidence product

Updated 2 November 2026. **Receiving software implemented and locally rehearsed; customer deployment and field validation remain open.** [Implementation status](IMPLEMENTATION_STATUS.md). [Implementation plan](plans/delivery-evidence-reshape.md) ·
[Roadmap](../ROADMAP.md) · [Pilot](PILOT_PROPOSAL.md).

## Product promise

Know what was recorded at the gate, what the receiver accepted, and what still needs resolving.
SitePulse connects a planned construction delivery to its arrival, quantity/condition evidence,
receiver confirmation and document references. The first output is a traceable receipt packet.
Confirmation identifies an accountable person; it is not independent or legal certification.

## First customer and job

One contractor, one site, one receiving gate and one material family. The project director or
procurement lead is the prospective buyer. The receiver records arrivals; the coordinator
handles exceptions; the accountant uses the evidence. Select the location by access to a real
pilot host. These roles and willingness to pay remain hypotheses until interviews/pilot evidence.

**Primary job:** when a delivery arrives or is disputed, record the facts and disagreements once
so the site and office can decide what to accept and what to investigate.

## MVP scope and acceptance

| Capability | Acceptance boundary |
|---|---|
| Delivery register | Stable site/delivery IDs; supplier/material lines; quantity and unit; promised date or time window with honest precision. Works without a prediction or 1C integration. |
| Phone receiving | QR/reference lookup, unexpected-load fallback, arrival claim, observed quantity/condition, photo/ticket and visible location availability. |
| Named confirmation | Authorised receiver confirms an exact revision/quantity or disputes it. Driver acknowledgement remains a future, separately attributed extension. |
| Partial receipts | Multiple arrivals per order, accepted vs expected quantities and explicit completion; no automatic conversion of a partial load into full delivery. |
| Offline capture | After initial online setup, local draft/media survive reload; retries do not duplicate receipts; unsent, failed and conflicting records remain visible. |
| Today and exceptions | Expected arrivals, missing confirmations, unmatched references and discrepancies. Unknown responsibility remains unknown. |
| Traceable history | Corrections create revisions; old evidence stays visible; changed evidence cannot silently retain confirmation. Same-ID/different-content upload conflicts. |
| Receipt packet | Current status, plan/actual, evidence, actors, revisions, manual document references and digest manifest; access-controlled export. |
| Field readiness | Site-scoped access, revocation, private media, customer deployment and tested DB/media recovery before real intake. |

Sync, evidence and operational states are separate. “Saved on device” is not “received by
server”; “recorded” is not “receiver-confirmed”; “arrived” is not “accepted in full”.
REAL/SIM labels describe origin, not truth. Time and location from a phone carry their own
limitations. Do not infer fault or fraud from lateness, a mismatch or a missing document.

## Keep from the current prototype

- Historical CSV audit: quality report, supplier/material scorecards, confidence intervals and
  chronological comparison with a supplier baseline. It is optional onboarding, not a pilot prerequisite.
- Tenge exposure with user-supplied inputs; exposure is not measured savings.
- Signed machine arrival intake and prediction/outcome loop as legacy integration primitives.
- Fixed-time equipment scheduling and phase checks as supporting tools, outside the first capture flow.
- Public synthetic example; the static console is the product and Streamlit the internal analyst surface.

The legacy gate payload remains date-only and applies arrivals to predictions. The new receiving
contract separately implements named confirmation, offline media, evidence packets and migrations.
See the historical [source-backed gap table](plans/delivery-evidence-reshape.md#3-code-baseline-and-the-actual-gaps).

## Not in the first release

Direct ЭСФ/СНТ/ЕСУТД or 1C APIs; automatic accounting acceptance; bank underwriting or payment
release; cross-company credit scores; an equipment marketplace; energy sensors; face recognition;
full ERP replacement; shared multi-tenant operation. Manual document references are sufficient
for the pilot. Later expansion requires the [roadmap gates](../ROADMAP.md).

## Success and boundaries

Measure all arrivals independently of app use. Report recorded coverage separately from complete
confirmed coverage; target at least 60% complete confirmed coverage and investigate below 30%.
Record capture burden, sync failures, correction/dispute handling and whether the buyer uses the
record for a real decision. These are proposed targets, not achieved results.

Public Railway remains synthetic-only. Customer hosting in Kazakhstan/on-prem, permission,
retention and a named site owner remain project prerequisites. SitePulse does not promise
document legal validity, shorter payment time, measured savings or a production SLA based on
the existing synthetic benchmark. The [pilot protocol](PILOT_PROPOSAL.md) defines the evidence
needed for a continue/change/stop decision.
