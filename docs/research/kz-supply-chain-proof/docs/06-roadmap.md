# 06 · Roadmap and decision gates

Dates assume a start on 1 November 2026. Numbers are suggestions to be adjusted after the first pilot.

## Phase 0 · Validate (2 weeks, November 2026)

- Ask the judge who raised the bank point for 15 minutes: which team, which reports, what is missing.
- 10 interviews: 4 site or project managers, 3 suppliers, 2 carriers, 1 bank officer (script in `07-visibility-plan.md`).
- Design the gap test (see `05-delivery-vs-banks.md`).
- Check your legal-entity status and each program's rules on company registration and who may be a director.

**Gate 0:** at least 6 interviews done and at least 2 people willing to host a pilot. If not, change the target segment before building more.

## Phase 1 · Prove the event (November to December 2026)

- MVP: gate event (QR, photo, time, GPS, sign-off), offline-first, planned-versus-actual view.
- 1 to 2 pilot sites, free for 30 days.
- Collect the gap-test dataset.

**Gate 1:** at least 60% of deliveries on the pilot site have a verified event. If under 30%, fix the workflow (who scans, where, when) before adding features.

## Phase 2 · Connect to money (January to March 2027)

- Match events to ЭСФ/СНТ numbers; reconciliation exceptions list.
- Supplier score with confidence.
- Read-only bank API, consent-based; one design-partner conversation with a bank, MFO or factor.
- Applications: the national startup battle (the 2026 cycle took applications until late February, so expect a similar window), Astana Hub programs (check eligibility and current rounds), AIFC Tech Hub, and the BI Group and MOST scouting program.

**Gate 2:** at least one bank, MFO or factor willing to test the VDC on real invoices, or at least 3 suppliers asking for it. If not, keep the operations product for developers and delay the fintech layer.

## Phase 3 · Be seen and be paid (April to June 2027)

- AstanaBuild, 28 to 30 April 2027, EXPO Astana: attend as a visitor or exhibit, and book meetings in advance.
- ЕСУТД-ready mode for carriers before the 1 June 2027 date.
- First paid pilot or subscription.

**Gate 3:** at least one paying customer, or a signed paid pilot.

## Phase 4 · Energy and hardware (second half of 2027)

- Energy per delivery from existing sensors.
- One hardware pilot: power-quality logger, clamp-on current sensor on a pump or generator, or a scale gateway.
- Energy ledger as an add-on to existing customers, not as a separate sale.

## Hardware rules

1. Use hardware only where a phone cannot give trusted data.
2. One hardware product at a time, built from off-the-shelf parts.
3. Do not buy parts until a pilot site agrees in writing.
4. Plan for −30°C, dust, vibration, theft and calibration. State accuracy honestly.
5. Check Kazakhstan's rules for radio modules and electrical safety before deployment.

## What not to do yet

- Do not lend money or hold funds.
- Do not run face recognition or collect biometrics without explicit consent and legal review. Keep monitoring that has no personal data separate from anything that does.
- Do not pitch mining, steel and construction at the same time. Pick one sales cycle.
- Do not publish a customer's data or name without written permission.

## KPIs

| Level | Metric |
|---|---|
| Activity | Interviews held, pilots live, deliveries recorded |
| Product | % deliveries with a verified event, queue minutes, late loads flagged 24 h ahead |
| Money | Days from delivery to payment, reconciliation hours saved, paid pilots |
| Reach | Repo stars and forks, unique readers, inbound messages from target companies |
