# SitePulse: delivery evidence first

2 November 2026 · Product proposal and implementation backlog · **Original planning baseline; implementation update below.**

Start with the [product requirements](../PRD.md), [roadmap](../../ROADMAP.md) and
[pilot protocol](../PILOT_PROPOSAL.md). This plan supersedes the **future work order** in
[the October plan](mvp-reshape.md); its completed work and historical notes remain valid records.

> Implementation update, 2 November 2026: the user subsequently authorised full software implementation.
> See [current status](../IMPLEMENTATION_STATUS.md) and [runbook](../RECEIVING_RUNBOOK.md).
> The code baseline/gaps below describe the original planning snapshot, not the current checkout.
> Optional E7–E9 software is disabled by default; field and partner gates are not claimed complete.

## 1. The product decision

**SitePulse helps a construction site's receiving team record a delivery, confirm what was
accepted, and resolve discrepancies using one traceable evidence record.**

The first buyer hypothesis is a contractor's project director or procurement head. The daily
user is the receiver/gate coordinator; the accountant uses the resulting record. Suppliers and
carriers benefit from an explicit receipt and a record of waiting. Banks are potential later
data consumers, not the first buyer or a promised partner.

Keep the SitePulse name. Treat `delivery-delay` as the existing repository name; renaming it
does not help validate the product. Lead with receiving and dispute resolution. Keep historical
supplier audits as an optional entry service, and prediction/scheduling as supporting capabilities.

The research spans logistics, finance and energy. The build should follow their dependency:
**capture useful delivery evidence → reconcile documents → test external demand → add further services.**
It should not launch three products at once.

| Decision | Proposed choice | Why / what would change it |
|---|---|---|
| First market | One contractor, one site, one receiving gate and one material family | Allows observation of the complete workflow; expand only after adoption. |
| Location | The site the founder can visit regularly; Karaganda, Astana or Almaty are candidates | The October plan preferred Karaganda; the new research names Astana/Almaty. Access to an actual host should decide. |
| First promise | A usable arrival/acceptance record and a visible exception queue | Payment acceleration and loss reduction remain outcomes to measure. |
| Entry route | Observe receiving; offer the existing historical audit if useful | A missing 1C export must not prevent a delivery-capture pilot. |
| Interface | Phone capture + the existing Russian-language product console | A new frontend framework is not a prerequisite. |
| Revenue hypothesis | Contractor pays per active site; participating suppliers/carriers do not pay to confirm | Test a concrete paid continuation with the buyer. No validated price exists. |
| Bank role | Interview now; restricted evidence sharing only after demand and access controls exist | Neither legal acceptance nor underwriting usefulness is established. |
| Energy | Later add-on at an existing customer | No sensor purchase or energy platform in the first delivery pilot. |

## 2. What changes from the October direction

| October direction | November proposal |
|---|---|
| First output: scorecard from a 1C export | First operational output: delivery record with acceptance/discrepancy evidence |
| Arrival closes a prediction outcome | Delivery exists and can be received without any prediction |
| Roles and slot approval follow migrations | Named receivers, event history and capture follow migrations; slots come later |
| Daily at-risk list centres model output | Today centres expected, arrived, awaiting confirmation and disputed loads |
| Evidence = an arrival date and audit entry | Evidence includes time provenance, quantity/unit, attachments, actors and revisions |
| Multi-site after a successful pilot | Still deferred; a portable cross-builder score is not an MVP |

Keep: CSV import, quality reporting, scorecards with uncertainty, model-vs-baseline checks,
exposure arithmetic, fixed-time scheduler, deterministic phase checks, signed machine ingestion,
the synthetic example and one isolated deployment per customer. None needs a rewrite to validate
the new product. A narrow operational delay metric must remain distinct from the existing
date-level/material-grace ML label.

## 3. Code baseline and the actual gaps

Inspected base: `cdd457adf5adacc42976b07ffc8be2a608500095` on `main`.
This is a source review, not a fresh runtime or production certification. Graph coverage was
checked for the evidence files; excluded static HTML was inspected directly.

| Current source | What it provides | Work required for this product |
|---|---|---|
| [`api/routers/integrations.py`](../../api/routers/integrations.py), `GateEvent`, `gate_events` | HMAC-authenticated batches; `event_id`, `delivery_ref`, **date-only** `occurred_on`; duplicate counting and unmatched queue | A versioned capture contract with timestamps, quantities, attachments and confirmation; preserve the legacy endpoint. |
| [`api/routers/monitoring.py`](../../api/routers/monitoring.py), `apply_outcome` | Finds the latest `PredictionLog` by reference and writes its outcome | Receive against a stable delivery identity even when no prediction exists; derive model outcomes separately. |
| [`db/models.py`](../../db/models.py), `Delivery`, `IntegrationEvent`, `AuditEvent` | Date-based delivery fields; source/event uniqueness; audit rows | Planned time windows, line quantities/units, evidence revisions, named attestations and provenance. Existing audit rows are not a cryptographic proof of physical arrival. |
| [`db/database.py`](../../db/database.py), `init_db` | `create_all` table creation | Versioned upgrades and preservation of existing data before schema changes. |
| [`api/security.py`](../../api/security.py) | Admin key and workspace-key helpers | Site-scoped permissions and attributable receiver/reviewer identities; shared admin credentials cannot establish who accepted a load. |
| [`ml/scorecard.py`](../../ml/scorecard.py) | Counts, on-time shares, Wilson intervals and trends | Retain these; later distinguish imported history from field-confirmed observations. This is not a portable credit score. |
| [`ml/ingest.py`](../../ml/ingest.py), [`ml/audit.py`](../../ml/audit.py) | Historical CSV preparation and report generation | Keep historical audit separate from an upcoming-delivery register; design a minimal schedule import only after seeing a pilot's sample. |
| [`static/index.html`](../../static/index.html) | Existing console and historical CSV upload | Phone receiving form, delivery detail, sync status and exception work queue. The inspected console has no offline capture implementation. |
| [`tests/test_integrations.py`](../../tests/test_integrations.py) | Existing contracts for signatures, replay, retry and outcomes | Add conflict, concurrency, scoping, revisions and no-prediction receiving cases without breaking these contracts. |

An existing duplicate ID is currently counted as a duplicate without comparing its content.
The new contract must distinguish **same ID + same content** (safe retry) from **same ID +
different content** (conflict). This is planned hardening, not a claim that the current intake
already enforces it.

## 4. The first complete workflow

1. **Plan:** a coordinator creates/imports expected deliveries with site, supplier, material,
   expected quantity/unit and promised date or time window. Preserve date-only precision when
   that is all the source provides.
2. **Identify:** the receiver scans a delivery QR or searches by reference. QR identifies a
   record; it does not grant acceptance permission. Unexpected loads can be captured unmatched.
3. **Record:** capture arrival time, quantity actually observed, condition and a photo or ticket.
   Show whether location was available and how time was obtained. Permit incomplete records,
   but expose what is missing.
4. **Confirm:** an authorised receiver accepts the specified lines/quantities or opens a
   discrepancy. A driver acknowledgement is a separate optional attestation. Neither silently
   overwrites the other's account.
5. **Review:** a coordinator matches unknown references, reviews conflicts and assigns a
   reason/outcome. Unknown responsibility is allowed; lateness alone does not prove fault.
6. **Use:** the office compares plan and actual, follows open discrepancies and exports a
   versioned evidence packet. Manual document references are enough for the pilot.

Partial loads and multiple arrivals are normal: one order can have several physical receipts.
Accepted quantity must not silently become ordered quantity. A short receipt is not automatically
a closed order. Agree completion/cancellation explicitly with the coordinator.

## 5. Evidence rules that shape the implementation

These are **proposed contracts**, not existing database columns or endpoints.

| Record | Minimum meaning |
|---|---|
| Delivery plan | Stable site-scoped ID, external references, supplier, material lines, expected quantities/units, promised window or date plus its precision, plan version |
| Receipt event | ID, site and delivery link (nullable until matched), event kind, observed time + offset, server receipt time, actor/device/source, REAL/SIM provenance, observed quantities and condition |
| Attachment | Receipt/revision link, content digest, media type, size, storage reference, capture/upload timestamps and uploader; photo capture time is a claim unless independently supported |
| Attestation | Named actor, role, exact receipt revision/lines, accepted or disputed quantity, decision, time and reason; later edits cannot inherit old confirmation silently |
| Document reference | Document kind/number, issuer and relevant line reference, source precision, issue/confirmation dates when available; linkage is not a validated state-system match |
| Correction/dispute | Original event reference, reason, author, time and replacement/review outcome; preserve the original record |

Separate three independent dimensions:

- **Sync:** saved on device / pending upload / received by server / failed or conflicted.
- **Evidence:** recorded / receiver-confirmed / disputed / superseded. Confirmation is a named
  person's attestation, not independent certification. Show completeness and exceptions alongside it.
- **Operations:** expected / arrived / unloading / departed / partially received / completed or cancelled.
  Optional operational timestamps stay unknown when unobserved.

The pilot's stricter **complete confirmed receipt** metric requires a resolved delivery match,
time with explicit provenance, material quantity/unit, an available photo/ticket, and an authorised
receiver confirmation of the current revision. Missing GPS is visible but does not by itself block
confirmation. Missing evidence excludes the receipt from this stricter metric, even if someone
accepted the goods operationally. Disputed or superseded revisions do not count as current confirmed receipts.

Additional acceptance rules:

- Capture works without a prediction, trained model, 1C connection, or bank integration.
- Use decimal quantities and explicit units; never silently add tonnes to kilograms or infer conversions.
- Preserve device-observed and server-received times separately. Flag clock disagreement and late
  sync; never replace the physical arrival claim with upload time. Historical dates do not become
  invented midnight timestamps.
- A photo, location, QR, HMAC or hash alone cannot prove the shipment's contents or rule out collusion.
  Preserve raw evidence and label who asserted what. Do not market the MVP as independent verification.
- Retries reuse a stable event ID and canonical content digest. Concurrent identical retries produce
  one accepted event; conflicting reuse is surfaced. Machine request nonces remain distinct from event IDs.
- New evidence is append-only through normal application actions; corrections create revisions.
  Export a manifest with digests. Privileged database access remains a trust boundary; stronger
  anchoring and external attestation require a later threat model and review.
- REAL means captured in the customer workflow; it does not mean true or confirmed. Imports carry
  their source. SIM records never count in pilot, supplier or external-consumer metrics.
- Never put the shared machine-ingest secret or admin key in a phone's offline queue. Store only
  required drafts/media; authenticate sync, handle revoked/expired access and expose unsent records.
- Agree local draft retention and device-loss handling before field use. Cache the app shell, not
  unrestricted customer responses. Clear device data at sign-out only through a flow that warns
  about pending uploads and offers recovery.

## 6. Product surfaces

Keep the existing console and design tokens. Proposed Russian navigation:

| Surface | Primary action / decision | Release |
|---|---|---|
| Сегодня | Find expected/late arrivals, missing confirmations and unresolved discrepancies | MVP |
| Приёмка | QR or reference → arrival → quantity/condition → evidence → receiver confirmation | MVP, phone-first |
| Поставки | Inspect one delivery's plan, receipts, revisions, attachments and document references | MVP |
| Расхождения | Resolve unmatched, short, damaged, disputed or conflicting receipts | MVP |
| Поставщики | Existing scorecard with sample count and uncertainty; distinguish provenance | Existing audit retained; field-data integration later |
| Документы | Match imported invoice/consignment rows and inspect exceptions | After the receiving pilot |

The MVP delivery detail includes a printable/exportable receipt packet. Do not label it a legally
recognised certificate. “Verified Delivery Certificate” (VDC) remains a research term until the
recipient and appropriate review establish what that label means.

Keep the public synthetic audit demo accessible during implementation. A new landing message or
navigation order should ship with a working receiving flow, not imply that this planning pass
has delivered one. Streamlit remains an internal analyst tool.

## 7. Sequenced implementation backlog

The table below is the original acceptance backlog. Current delivery evidence is recorded in
[implementation status](../IMPLEMENTATION_STATUS.md); V0/V1 and customer release gates remain open. Ownership is a responsibility, not a
claim that a team member has been assigned. Finish and verify one bounded slice at a time.

| ID | Owner / dependency | Change boundary | Done when |
|---|---|---|---|
| V0 | Founder; first | Discovery and [pilot protocol](../PILOT_PROPOSAL.md) | Observe receiving, complete ≥6 relevant interviews, identify one named host and backup candidate, agree a material family, receiver and denominator. No host: narrow/revise before building field features. |
| E1 | Backend; V0 | `db/database.py`, models and proposed migration directory | Baseline migration upgrades both a new DB and a populated copy; row counts/references preserved; backup restores; rollback/recovery documented. Alembic was subsequently selected and installed; see implementation status. |
| E2 | Backend + product; E1 | Site/actor access and stable delivery register; `api/security.py`, schemas/models, proposed delivery router | An authorised receiver sees only assigned site data; rejected roles/cross-site IDs cannot read media or export; references can be created without a prediction. Revocation works. |
| E3 | Backend; E2 | Receipt contract, revisions and attachments; integrations/monitoring seam | Capture a receipt without `PredictionLog`; same-ID retry is idempotent under concurrency; changed-content retry conflicts; partial receipts and unknown refs persist; corrections retain originals; legacy signed intake still passes. |
| E4 | Frontend + backend; E3 | `static/` phone flow and delivery/exception views; minimal receipt export | Phone user records, confirms/disputes, reviews and exports the current revision; names/units/missing evidence are clear; camera denied and QR unavailable have fallbacks; no secrets appear in URLs or media links. |
| E5 | Frontend + backend; E4 | Offline app shell, durable draft/media queue and sync | On a pilot phone, after initial online setup: airplane-mode capture survives reload; reconnect uploads once; partial media upload, clock drift, quota/storage failure, revoked access and conflict remain visible and recoverable. No silent loss or false “synced”. |
| E6 | Operator; E1–E5 | Isolated customer deployment and recovery runbook | TLS, access/revocation, attachment and DB backup/restore, retention and no synthetic seeding checked in the customer stack; site owner accepts the workflow. Real data stays out of the public demo. |
| V1 | Founder + site owner; E6 | 30-day pilot, coverage and exception reporting | Report independent denominator, recorded/confirmed coverage, burden, timing quality and discrepancy outcomes; buyer makes continue/change/stop decision. No invented savings or live model accuracy. |
| E7 | Backend + accountant; V1 and explicit reconciliation need | Manual/CSV ЭСФ/СНТ/invoice line matching and exceptions | Split receipts, multiple documents, quantity/unit differences and ambiguous references remain reviewable; no fuzzy auto-confirmation; compare handling time to baseline. No state-system submission promised. |
| E8 | Backend + partner owner; E7 and evidence consumer | Restricted read-only packet/API, consent and access history | A real recipient agrees necessary fields; consent scope, expiry/revocation, site isolation and access logging verified; SIM excluded; recipient evaluates a real authorised packet. No lending/payment action. |
| E9 | Product; repeated customer demand | Human-approved slots, notifications, calibrated supplier history | Add only the requested operational constraint; preserve overlap checks and model-vs-baseline gates. Cross-builder scoring and energy remain separate decisions. |

**First engineering slice after validation:** E1 migrations. **First user-visible slice:**
E2–E4, a delivery planned and received online with a named confirmation and evidence packet,
independent of the model. This online slice is a controlled rehearsal; the poor-connectivity
field pilot still requires E5 and E6.

Preserve existing stack/layer boundaries and legacy contracts. Select dependencies when the
relevant slice has a concrete design; the later implementation instruction authorised the selected software dependencies, but no
production deployment has been performed. Do not use a shared role key as a substitute for a named attestation.

## 8. Validation and release evidence

Implementation should retain the current suite and synthetic-report check. Add meaningful tests
at the changed seams: migration preservation on Postgres, actor/site access including media,
no-prediction receipt capture, concurrent retries, altered-payload conflicts, correction history,
stale confirmations, partial loads, units, SIM exclusion and export redaction.

Browser/device verification is required for capture, keyboard/touch access, denied camera/GPS,
offline reload, interrupted media sync, quota failure and session revocation. An API test alone
does not establish a usable gate workflow. Every slice records code version, checks run and
remaining limitations. The planning pass itself needs document/link/consistency checks, not a
claim that new runtime behavior has been tested.

## 9. Commercial and expansion gates

The contractor pays only if the record helps a real receiving or accounting decision. Test a
site subscription or a fixed-scope paid continuation after the pilot. The older
150,000–300,000 ₸/site/month range is retained only as a founder pricing hypothesis; do not
present it as a validated willingness-to-pay result or a quote.

- **Discovery gate:** a site owner commits access, a receiver and a comparison process. Verbal
  enthusiasm or a bank conversation does not replace a pilot host.
- **Adoption gate:** target ≥60% complete confirmed coverage; below 30% triggers workflow repair
  before expansion. Also report simple recorded-arrival coverage separately (aspiration ≥80%).
- **Value gate:** the buyer demonstrates use in an actual decision and accepts a priced next step,
  or explains why the product is not worth paying for. Do not convert an LOI into revenue.
- **Finance gate:** one bank/factor/MFO agrees to evaluate specified evidence against a real
  authorised case, or repeated supplier demand justifies further discovery. Supplier interest
  alone does not establish bank acceptance. No money is lent, held or released by SitePulse.
- **Energy gate:** an existing customer identifies a per-delivery measurement decision and
  agrees a bounded sensor pilot. No hardware purchase is part of this plan.

## 10. Source boundaries and remaining decisions

The [31 October research packet](../research/README.md) supplies the new direction. Its market,
bank and regulatory assertions are **not revalidated by this source-code review**. No release
date depends on the claimed ЕСУТД deadline, interest rate, grant round or event date. Verify
current primary sources before those claims drive compliance, applications or public copy.

The packet's “document gap” is a hypothesis. Document issuance/confirmation time and physical
arrival time describe different events; a difference alone is not fraud or product demand.
The pilot tests whether the additional record changes a decision and is worth its capture cost.

Before implementation, discovery must settle: accessible pilot location; material family and
units; who receives/accepts goods today; phone ownership and connectivity; acceptable evidence
and retention; discrepancy responsibility; and a buyer's measurable use. Hosting and legal
acceptance are deployment decisions requiring the relevant review, not facts established here.

Decision outcome today: a bounded receiving product and a gated backlog. No partnership,
customer adoption, independent verification, legal certificate or payment benefit is claimed.
