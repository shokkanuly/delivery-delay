# SitePulse — delivery-evidence roadmap

Updated 3 November 2026. **Software implemented and verified locally and in CI; field/deployment gates remain open.**
[Remaining task register](docs/REMAINING_TASKS.md) · [Current implementation status](docs/IMPLEMENTATION_STATUS.md) · [Operator runbook](docs/RECEIVING_RUNBOOK.md).
[Product scope](docs/PRD.md) · [Source-backed backlog](docs/plans/delivery-evidence-reshape.md) ·
[Pilot protocol](docs/PILOT_PROPOSAL.md).

The existing CSV audit, supplier scorecards, historical backtest and exposure calculator remain.
Signed arrival intake and scheduling are reusable primitives. The new priority is a complete
receiving workflow that works without a model: **plan → record → confirm/dispute → review → export**.

E1–E6 software foundations are present. E7–E9 have optional implementations behind disabled flags.
The tables below retain the validation sequence: writing software does not complete V0/V1 or
justify enabling extensions for a customer. Customer hosting, physical-phone checks and partner
acceptance remain outstanding.

## First 90 days, conditional on a pilot host

This is a planning envelope from an agreed start, not a promised launch date. Founder-led
discovery starts first; field engineering follows the access and workflow gate. If capacity or
a gate slips, move the dates and keep the prerequisite intact.

| Window | Deliverable / backlog IDs | Exit gate |
|---|---|---|
| Days 1–14 | Observe receiving; ≥6 interviews across site/procurement, supplier/carrier and accounting; one bank discovery conversation if accessible. V0. | One host, named receiver, material family, data permission and independent arrivals denominator; backup candidate identified. No host: revise segment/scope. |
| Days 15–28 | Migration/recovery baseline, actor/site access and delivery register. E1–E2. | Existing data survives upgrade/restore; permissions and revocation verified; delivery creation needs no prediction. |
| Days 29–42 | Online receipt capture, attachments, partial loads, confirmation/disputes, revisions and export. E3–E4. | A complete rehearsal on synthetic data passes, including conflicts and denied access. |
| Days 43–56 | Offline queue and phone verification; isolated customer stack. E5–E6. | No silent draft loss or duplicate sync; DB and attachments restore; host approves field use. |
| Days 57–86 | One 30-day site pilot. V1. | Independent coverage, capture burden, evidence gaps, discrepancy outcomes and buyer feedback recorded. |
| Days 87–90 | Joint results and priced continuation discussion. | Continue/change/stop decision. Paid continuation is a target, not presumed revenue. |

For a small team, E1–E6 may take longer than this envelope. A narrower pilot or delayed start
is preferable to claiming offline readiness or evidence integrity before verification.

## After the receiving pilot

| Work | Opens when | Remains excluded |
|---|---|---|
| Document reconciliation (E7) | Accountant demonstrates repeated manual matching pain and provides permitted sample rows | Automatic state-system submission or legal acceptance claims |
| Read-only external evidence (E8) | A named bank/factor/other recipient agrees a specific evaluation; access/consent boundaries are ready | Lending, holding funds, automatic payment release |
| Slots and notifications (E9) | Site demonstrates that queues/coordination are the next constraint | Full logistics marketplace or autonomous booking decisions |
| Field-backed supplier analytics | Enough resolved records with provenance and stable definitions | Portable creditworthiness claims from sparse or disputed data |
| Energy/hardware | Existing customer agrees a concrete measurement use and bounded pilot | Buying hardware before a host or launching a second product |
| Several sites/shared tenancy | Repeated paying-customer needs justify the operating cost | Expanding merely to match a pitch deck |

## Metric gates

- Track all independently observed arrivals, including unplanned and unrecorded loads.
- Complete confirmed receipt coverage target: **≥60%**. Below **30%**, repair the workflow
  before adding integrations. Recorded arrival coverage is separate, with an **80% aspiration**.
- Record actual capture time, unmatched/conflicted records and missing attachments. Set acceptable
  burden with the receiver before launch; a provisional target is a median ≤90 seconds per routine load.
- Show one demonstrated operational/accounting use and a buyer's commercial decision. Timing
  differences alone do not prove fraud, useful evidence or savings.
- No new live model accuracy claim from the 20–50-load gap-test sample. The earlier ≥100 resolved
  outcomes is a minimum reporting gate, not proof of statistical validity or model superiority.

## Execution rules

E1 migrations, scoped named access and a separate offline receiving shell now implement the
engineering sequence. Keep the current stack/domain boundaries and preserve the legacy ingest
contract. Finish the host/device/recovery validation before customer intake; extensions remain
conditional on the detailed backlog's field gates.

The [October plan](docs/plans/mvp-reshape.md) is retained for completed stages/history; its
uncompleted stage order is superseded. Regulatory dates, program deadlines and rates in the
[research snapshot](docs/research/README.md) are not release commitments and require current
primary-source verification before use.
