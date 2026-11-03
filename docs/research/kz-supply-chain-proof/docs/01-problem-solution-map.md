# 01 · Problem to solution map

Each row links a problem to what can be built, who would pay or benefit, and the first number to measure. Full explanations are in `02-logistics.md`, `03-fintech.md` and `04-energy.md`. The same table is in `data/problems.csv`.

Confidence: **C** = confirmed by a source, **L** = likely (needs testing), **U** = unverified.

## Logistics

| ID | Problem | Conf. | Solution | Who benefits | First metric |
|---|---|---|---|---|---|
| L01 | Paper TTN with no arrival proof | L | Gate event: QR, photo, time, GPS, receiver sign-off, tamper-evident log | Developers, suppliers, banks | % of deliveries with a verified event |
| L02 | Gate queues and idle cranes | L | Arrival slots plus crane and bay scheduler | Developers, carriers | Queue minutes per truck; crane idle hours |
| L03 | Late or out-of-sequence loads | L | Delay-risk bands and planned-versus-actual view | Developers | % of late loads flagged 24 h ahead |
| L04 | ЕСУТД registration due 1 June 2027 | C | "ЕСУТД-ready" mode: draft TTN and waybill data from the gate scan | Carriers | Carriers onboarded before the deadline |
| L05 | Short loads and quality disputes | L | Scale ticket and photo capture, certificate link | Developers, suppliers | Disputes per 100 deliveries |
| L06 | No warehouse or yard space | C | Just-in-time delivery windows for sites without storage | Developers, suppliers | Out-of-sequence arrivals per week |
| L07 | Weak foreign trade, rising freight prices | C | Position for domestic construction freight; utilisation data later | Carriers | Share of trips with load data |
| L08 | Empty return trips, fragmented carriers | L | Back-haul matching (later, not now) | Carriers | Empty-run share |
| L09 | Fuel use and unverified mileage | L | GPS trace plus optional fuel sensor | Carriers, developers | Litres per delivery |
| L10 | No shared reliability data | L | Supplier and carrier score with a confidence level | Developers, banks | Score coverage of active suppliers |

## Fintech

| ID | Problem | Conf. | Solution | Who benefits | First metric |
|---|---|---|---|---|---|
| F01 | Fake or backdated delivery documents behind financing requests | L | Verified Delivery Certificate (VDC) tied to the gate event | Banks, MFOs, factors | Mismatches caught per 100 invoices |
| F02 | Costly working capital | C | Faster verified invoices, so a partner funds against delivery | Suppliers | Days from delivery to payment |
| F03 | No supplier track record for SMEs | L | Empirical Bayes score with confidence, bank API | Banks, suppliers | Suppliers with a usable score |
| F04 | Manual 1C, ЭСФ and bank reconciliation | L | Auto-match event to ЭСФ/СНТ numbers and payment | Developers, suppliers | Hours of reconciliation saved |
| F05 | Bank factoring anchored to contracts, not site delivery | C/L | Data partnership, not competition | Banks | Banks piloting the VDC |
| F06 | Milestone and payment-release disputes | L | Delivery evidence for technical supervisors and funders | Developers, state funders | Disputes closed per week |
| F07 | Consumer fraud and dropper schemes | C | Out of scope; keep sign-off identity checks lean | Everyone | n/a |
| F08 | Late interbank QR adoption (now connected) | C | Enables pay-on-delivery later | Suppliers | Pilot payment triggers |
| F09 | Licensing and AML burden for lenders | L | Partner with licensed institutions; AIFC sandbox | The company | Partner agreements |

## Energy

| ID | Problem | Conf. | Solution | Who benefits | First metric |
|---|---|---|---|---|---|
| E01 | Electricity deficit | C | Site and plant energy visibility, peak awareness | Plants, developers | kWh per site per week |
| E02 | Worn grid, outages | C | Power-quality logger at the site gate or plant | Developers, plants | Outage and sag events logged |
| E03 | Heat-network wear and winter heating cost | C/L | Per-pour curing and heating energy tracking | Developers | kWh per cubic metre cured |
| E04 | Thin metering | C | Low-cost sub-metering on pumps, cranes, generators | Plants, developers | Assets metered |
| E05 | No digital expenditure accounting in tariff approval | C | Per-asset energy ledger (later, B2G) | Utilities, ministry | Pilot with a data standard |
| E06 | No energy or CO₂ per delivery | L | kWh, fuel and CO₂ per delivery | Developers, banks | Assets with CO₂ per delivery |
| E07 | Pump and equipment waste or wear anomalies | L | Anomaly detection plus controller | Plants | kWh saved per pump |
| E08 | ESG and green-finance evidence | L | Auditable ledger, FEED versus SIM tags | Developers, banks | Reports produced |
| E09 | Sector cybersecurity and air-gapped sites | C | On-prem, zero-external-call deployment | Plants, banks | Security reviews passed |

## Reading the map

- **Logistics first.** L01 to L04, F01, F04 share one data object, the verified delivery event.
- **Fintech second.** F01 to F05 get easier once events exist; do not lend, partner.
- **Energy third.** E06 and E07 reuse the same sensors; E01 to E05 are sector problems, not your first customers.
