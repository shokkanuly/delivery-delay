# One-site receiving pilot — discussion draft

2 November 2026. Proposed protocol, not a signed agreement. No host, customer result, price,
partnership or production SLA is established by this document.
[Scope](PRD.md) · [Implementation prerequisites](plans/delivery-evidence-reshape.md).

## The question

Does a traceable receipt captured at the gate help the site's receiver and accountant make a
better or faster decision, at a capture cost the site accepts?

Test this with one contractor, one site, one gate and one material family for 30 days after
field-readiness checks pass. Observe existing practice first. A historical 1C audit can help
onboarding but is optional; the pilot must also work without a prediction or ERP connection.

## Agree before day 1

| Decision | Record before launch |
|---|---|
| People | Buyer, site owner, receiver, reviewer and founder/operator; who covers missed shifts |
| Boundary | Gate, material family, units, planned vs unexpected arrivals and treatment of partial loads |
| Baseline | Existing receiving/document process, observed capture/reconciliation time, example dispute if available |
| Evidence policy | Required photo/ticket, quantity method, confirmation authority, treatment of missing GPS and time uncertainty |
| Data | Permission, access, storage/retention/deletion, device use, private media and permitted exports; customer hosting ready |
| Denominator | Independent gate sheet/register covering all eligible physical arrivals, including ones never entered in SitePulse |
| Targets | Coverage, burden and useful decisions; what triggers intervention or stopping |
| Commercial next step | Pilot duration/free or paid terms, review date and who can accept a priced continuation |

Use real records only in the approved customer deployment. Rehearse offline capture, access
revocation, media sync and DB/media recovery before starting. Keep public Railway synthetic.

## 30-day sequence

| Period | Activity | Evidence |
|---|---|---|
| Days 1–7 | Observe and train receiver; capture alongside the existing process | Baseline timing, all-arrivals register, missing fields and reasons for non-use |
| Days 8–21 | Routine capture and confirmation; review discrepancies daily | Named confirmations, revision history, partial receipts, sync failures and decisions |
| Days 22–27 | Review a consecutive sample of 20–50 eligible arrivals against documents | Gap-test table, missingness, traceable matching and explanations |
| Days 28–30 | Receiver/accountant/buyer review; propose priced continuation | Keep/change/stop decision and reasons; no implied savings or customer endorsement |

If fewer than 20 eligible arrivals occur, report the actual count and extend by agreement rather
than selecting extra favourable cases. Sample consecutively or select the window in advance;
record exclusions. SIM/test events are excluded throughout.

## Gap-test dataset

For each arrival: pseudonymous site and receipt IDs; order/delivery reference; supplier ID;
material; expected and observed/accepted quantities and units; planned date/window and precision;
device-observed arrival time and offset; server receipt time; location availability/accuracy;
source and REAL/SIM tag; attachment presence; actor and confirmation revision/status;
document type/number and relevant line; document issue date/time and precision; buyer
confirmation date/time if available; mismatch category; reviewer decision; payment date only
when permitted and actually known. Keep names/contact details outside publishable results.

Separate these comparisons:

1. **Operational:** arrival vs agreed window; optional unloading-start/departure to measure queue
   and service duration. Do not infer queue time when only arrival exists.
2. **Synchronization:** server receipt vs device time, with clock reliability caveats.
3. **Document timing:** issue/confirmation vs observed arrival, retaining date-only precision.
   Issue dates can legitimately precede delivery. Do not invent sub-day gaps from date-only values.
4. **Acceptance:** expected vs received vs accepted quantity; photo/ticket and material/grade
   discrepancies. Missing data is its own outcome, not an automatic mismatch.
5. **Usefulness:** what decision was made, by whom, and whether they could already make it from
   existing documents. A timestamp gap alone is not evidence of fraud or demand.

## Metrics with denominators

A physical truck arrival is one receipt opportunity. Multiple material lines do not multiply
that denominator; separate return trips do. Retain order-level partial/completion status separately.

| Metric | Definition | Proposed interpretation |
|---|---|---|
| Recorded coverage | Eligible arrivals linked to at least one non-SIM recorded receipt / all eligible arrivals in independent register | Report missed arrivals and duplicates; aspiration ≥80%. |
| Complete confirmed coverage | Eligible arrivals with a matched current receipt, quantities/units, time provenance, available photo/ticket and authorised receiver confirmation, without an open dispute / all eligible arrivals | Target ≥60%; below 30% triggers workflow repair. All received lines must be accounted for; missing optional GPS is disclosed. |
| Capture burden | Median and p90 observed staff time per receipt, including rework where measured | Provisional median ≤90 seconds for routine loads; agree after observing the baseline. |
| Sync reliability | Locally saved records eventually acknowledged / locally saved records; pending-age distribution and lost-record incidents | Track each failure; report unsent records rather than counting them as server evidence. |
| Discrepancy handling | Counts by category; time from opening to reviewed outcome; unresolved count | Describe usefulness; a 30-day sample need not show a causal reduction. |
| Document gap | Distribution for comparable timestamp pairs; number with only dates or missing values | Descriptive result with precision and missingness, not fraud detection accuracy. |
| Buyer value | Specific decisions supported, repeated use and accepted/rejected paid continuation | Capture the actual decision; an LOI is not revenue. |

Payment-time and reconciliation-time improvements are exploratory unless comparable baseline
cases and confounders are recorded. No inference of savings from the exposure calculator.
Do not publish live predictive accuracy from this small gap-test sample.

## Stop, repair or continue

- No accountable receiver, permission or safe customer deployment: do not begin real capture.
- Lost drafts/media, cross-site exposure or silent conflicting updates: suspend the affected
  workflow and fix it before resuming; retain an incident record.
- Below 30% complete confirmed coverage: inspect who scans, when and why records are incomplete
  before adding any bank or energy feature. Between 30–60%: agree a bounded workflow iteration.
- ≥60% coverage plus demonstrated use: discuss a priced continuation, not automatic expansion.
- No useful information beyond the existing workflow: narrow to an observed operations problem
  or stop the evidence product hypothesis. Publish anonymised results only with permission.

The earlier 150,000–300,000 ₸/site/month figure is an unvalidated founder hypothesis. Prepare one
concrete offer with scope/support at the review meeting; a free pilot does not test willingness
to pay. Bank evaluation and energy sensors are separate later agreements.
