# 05 · Delivery: what banks and state systems have, and what a verified-event platform can add

*Competitive brief · 31 October 2026 · ratings of other systems are hypotheses until tested.*

## The question

Feedback from a 2026 startup final said companies more often take information from banks than from projects like SitePulse, and that banks already have reports and documents on each company's purchases. Is that a reason not to build?

**Short answer:** banks are the right *partner and trust anchor*, not necessarily a substitute. Banks know **who paid whom, against which contract**. The open question is whether anyone independently records **what physically arrived, when, in what condition, and whose fault a delay was**. Sections 2 to 4 say how to find out.

## 1. What each system records (what we could confirm)

| System | What it records | Source | Confidence |
|---|---|---|---|
| Bank accounts and payments | Who paid whom and when | General | Confirmed (general) |
| Bank factoring (e.g. Halyk digital factoring, BCC) | A receivable under a contract; for Halyk, government procurement contracts | S11 | Confirmed (product descriptions) |
| ЭСФ (electronic invoice) and СНТ (consignment note) in the tax information system | Invoice and shipment declarations; the supplier issues the СНТ no later than the start of shipment; the buyer confirms or rejects it within a deadline | S5, S6 | Confirmed (rules summaries; deadlines differ by source) |
| Virtual Warehouse | Goods movement for listed goods; building materials were added in stages from 2022; a new list applies from 1 January 2026 | S5 | Confirmed |
| ЕСУТД | Registration of TTN and waybills; suspended until 1 June 2027 | S1 | Confirmed |
| E-Qurylys | State-ordered objects: documents, schedules, materials, e-acts, payment links | S3, S7 | Confirmed |
| Kazreestre and engineering companies (housing shared construction) | Contracts, non-cash payment checks, monitoring of progress and use of funds, volumes of work | S13, S14 | Confirmed |

**Important detail:** the buyer's confirmation of a СНТ is an accounting action in a system, with a deadline of days to weeks depending on the rule version. It is not the same as a time-stamped, geolocated record that a truck arrived at a gate. Check the current rule text on the tax authority's site before you quote this.

## 2. What these systems may not see (the hypothesis to test)

These are not claims about what banks "do not have". They are the open questions an interview or pilot should settle.

1. **Arrival time against plan, at the site.** An independent time stamp from the gate, not an accounting click days later.
2. **Quantity and condition at arrival.** Weight, photos, batch and certificate links.
3. **Forward-looking risk.** Bank and state data look back. A delay prediction looks forward.
4. **Cross-builder supplier reliability.** A bank sees its own clients. A neutral score can span builders and banks.
5. **Operational context.** Queue time and crane availability show whether a delay was the supplier's or the site's.
6. **Multi-party attestation.** Driver, receiver and supplier each confirm, in a tamper-evident log.
7. **Event-level, near real time data.** Not a monthly report.
8. **Dispute evidence.** One export that settles who is right.
9. **Energy, fuel and CO₂ per delivery.**
10. **Offline and on-prem use.** Sites have poor connectivity and strict security rules.

## 3. How to test it in 30 days (this is also your best evidence)

1. **Bank interviews (5).** Ask a factoring or SME team: "Which delivery data do you check before financing? What happens when goods are disputed? Would you accept a third-party delivery record?" Ask for a sample report.
2. **The gap test.** On one pilot site, take 20 to 50 deliveries. For each, record: (a) gate time, (b) ЭСФ date, (c) СНТ date and confirmation date, (d) planned time. Measure the gap distribution. If gate time differs from the document dates by hours or days, that table is your evidence. If it does not, you have learned something important early.
3. **A payment story.** Find one supplier who waited for payment because of a disputed delivery. Document it with permission.
4. **Publish the anonymised result** in this repo as a case study.

## 4. Feature comparison

Scale: Strong, Adequate, Weak, Absent. SitePulse ratings are the *target* you must prove in a pilot. Others are hypotheses.

| Capability | Verified-event platform (target) | Bank factoring | State systems (ЭСФ/СНТ, E-Qurylys, ЕСУТД) | 1C / ERP | Paper process |
|---|---|---|---|---|---|
| Payment and financing | Absent by design (partner) | Strong | Absent | Weak | Absent |
| Legal validity | Weak today | Adequate | Strong | Adequate | Weak |
| Trust and regulation | Weak today | Strong | Strong | Adequate | Weak |
| Independent arrival time at site | Strong (target) | Absent (hypothesis) | Weak (accounting click) | Absent | Weak |
| Quantity and condition evidence | Strong (target) | Absent (hypothesis) | Weak | Weak | Weak |
| Forward-looking delay risk | Strong (target) | Absent | Absent | Weak | Absent |
| Cross-builder supplier reliability | Adequate, Strong with data | Weak (own clients) | Weak | Absent | Absent |
| Crane and bay scheduling | Strong (target) | Absent | Absent | Weak | Weak |
| Energy and CO₂ per delivery | Adequate (later) | Absent | Absent | Absent | Absent |
| Offline and on-prem | Strong | n/a | n/a | Strong | Strong |

**Honest reading:** banks and state systems win on legal validity, money and trust. A new platform wins only on rows 4 to 8. So pitch it as a *bank-grade evidence feed*, not as a replacement.

## 5. What to build, match and skip

- **Build and accelerate:** gate event and offline capture; planned-versus-actual; reconciliation with ЭСФ/СНТ numbers; supplier score with confidence; a read-only bank API with consent.
- **Reach parity:** security (penetration test, access logs, data stored in Kazakhstan, on-prem option), legal clarity (data-sharing consent, personal-data rules), uptime and support.
- **Deprioritise:** lending, mining and metallurgy twins, face recognition (see the legal note in `06-roadmap.md`).
- **Monitor:** E-Qurylys changes, ЕСУТД status, whether banks add physical verification themselves.

## 6. Positioning

> Banks know who paid whom. We prove what physically arrived, when, in what condition, and whether the delay was the supplier's or the site's, so that banks and builders can decide faster with less risk.

Message layers: category (delivery verification), differentiator (independent and event-level), value (shorter payment and dispute cycle), proof (pilot numbers from the gap test).

## 7. Closing the trust gap with banks

| Their concern | What you show |
|---|---|
| Is the data tamper-proof? | Append-only log, hashes, FEED versus SIM tags, raw export on request |
| Is it secure? | Penetration test report, access control, data residency, on-prem option |
| Is it legal? | Consent flows, personal-data handling, no biometrics by default |
| Is it stable? | Uptime numbers, offline mode, support contact |
| Is it independent? | No payments from suppliers that change their scores; public scoring method |
| Has anyone used it? | Pilot results and a reference from a builder |

## 8. Strategic implications

1. Run the gap test before you pitch again. It replaces opinion with numbers.
2. Target a bank or MFO as a **design partner** for the VDC; do not try to win customers away from banks.
3. If the gap test shows no gap, fall back to the operations value (queues, cranes, delays) for developers and drop the fintech story for now.
4. Date every claim in this file and re-check it each quarter. Competitive analysis goes stale.
