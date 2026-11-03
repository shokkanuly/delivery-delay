# 02 · Logistics problems

Format for every problem: what happens, evidence, who feels it, possible solution, hardware option, first metric. Tags: **[CONFIRMED]**, **[LIKELY]**, **[UNVERIFIED]**. Source codes (S#) point to `08-sources.md`.

## Rules and documents

### L01 · Paper TTN with no arrival proof
- **Status:** [LIKELY]. Paper TTN and waybills stay valid while ЕСУТД registration is suspended (S1). Feedback from a 2026 startup competition also questioned what banks can actually verify.
- **What happens:** A delivery note is signed by whoever stands at the gate. Nobody records the exact arrival time, the real quantity or the condition. Later, supplier, carrier and builder each tell a different story.
- **Who feels it:** Site managers, suppliers waiting for payment, banks that finance the invoice.
- **Possible solution:** A gate event: QR on the TTN or truck, photo, time, GPS, receiver sign-off, stored in an append-only log, offline-first.
- **Hardware option:** A phone is enough to start. Add a scale gateway only where weight is the dispute (see L05).
- **First metric:** Share of deliveries with a verified event.

### L04 · ЕСУТД registration due 1 June 2027
- **Status:** [CONFIRMED]. Registration of TTN and waybills in ЕСУТД for trucks above 3.5 t was due on 1 June 2026, then suspended until 1 June 2027 by Order No. 189 of 23 July 2026. TTN and waybills must still be issued; they are just not registered (S1, S2).
- **What happens:** Carriers have to move from paper habits to a state system with tight deadlines, and many lack simple field tools.
- **Who feels it:** Trucking companies and drivers; shippers that depend on them.
- **Possible solution:** An "ЕСУТД-ready" mode: when the gate scan happens, prefill TTN and waybill data so the carrier can register it. Check the current ЕСУТД interface rules before promising integration.
- **Hardware option:** None needed.
- **First metric:** Carriers onboarded before June 2027.

### L06 · No warehouse or yard space
- **Status:** [CONFIRMED]. Vacancy in modern logistics parks in Almaty and Astana was only 0.5–0.7% in summer 2026 (S17).
- **What happens:** Construction sites in cities have no room to store material, so a truck that arrives early or out of sequence blocks the site.
- **Who feels it:** Developers, suppliers, carriers.
- **Possible solution:** Just-in-time delivery windows; slot booking; sequence rules ("rebar before formwork").
- **Hardware option:** None.
- **First metric:** Out-of-sequence arrivals per week.

## Operations on site

### L02 · Gate queues and idle cranes
- **Status:** [LIKELY]. A common field complaint; needs your own measurement.
- **What happens:** Trucks bunch up at the gate while a crane and crew wait, or the crane is busy while trucks idle.
- **Who feels it:** Developers (labour and equipment burn), carriers (unpaid waiting).
- **Possible solution:** Arrival slots plus a crane and bay scheduler (constraint solver such as OR-Tools CP-SAT). Record queue time per truck as primary data.
- **Hardware option:** BLE or RFID gate reader if phones are unreliable.
- **First metric:** Queue minutes per truck; crane idle hours per week.

### L03 · Late or out-of-sequence loads
- **Status:** [LIKELY].
- **What happens:** A late load stops a pour or a lift; an early load clutters the site.
- **Who feels it:** Site managers, project controllers.
- **Possible solution:** Delay-risk bands (green, yellow, red) from supplier history, route, time, weather; planned-versus-actual dashboard; alerts before the truck leaves.
- **Hardware option:** Optional GPS tracker on the truck, so the driver's phone is not the only signal.
- **First metric:** Share of late loads flagged at least 24 hours ahead.

### L05 · Short loads and quality disputes
- **Status:** [LIKELY].
- **What happens:** A delivery is short, damaged, the wrong grade, or batched too long ago (concrete). Evidence is a signature and a memory.
- **Who feels it:** Developers, suppliers, quality engineers.
- **Possible solution:** Capture the scale ticket and photos, link batch number and certificate, record time since batching for concrete.
- **Hardware option:** ESP32 gateway that reads a weighbridge indicator or load cell where the site or plant has one; mixer-drum and concrete-temperature sensors.
- **First metric:** Disputes per 100 deliveries.

### L09 · Fuel use and unverified mileage
- **Status:** [LIKELY].
- **What happens:** Fuel and trip claims are hard to check, especially across many small carriers.
- **Who feels it:** Carriers and the developers who pay per trip.
- **Possible solution:** GPS trace per delivery; compare with claimed mileage; optional fuel-level sensor.
- **Hardware option:** Fuel-level sensor, BLE tag, GPS tracker.
- **First metric:** Litres per delivery, variance between claimed and traced distance.

## Market and structure

### L07 · Weak foreign trade, rising freight prices
- **Status:** [CONFIRMED]. Export-import transport requests fell 32% year on year in Q1 2026 while domestic demand kept growing, and a new EAEU control order for transit and international freight started on 11 February 2026. Freight prices were up 3.8% in January 2026 (S17).
- **What happens:** Carriers compete harder for domestic jobs, margins are thin, and compliance load is rising.
- **Who feels it:** Carriers.
- **Possible solution:** Be useful to carriers early (queue pass, ЕСУТД-ready drafts, proof of waiting time) so they join the network.
- **Hardware option:** None.
- **First metric:** Share of carriers that use the driver app on a pilot.

### L08 · Empty return trips and fragmented carriers
- **Status:** [LIKELY]. Not sourced; treat as a hypothesis to ask carriers about.
- **What happens:** Many small operators return empty and cannot see each other's capacity.
- **Possible solution:** Back-haul matching. **Not now**: it is a marketplace, a different business.
- **First metric:** Empty-run share, if you ever measure it.

### L10 · No shared reliability data
- **Status:** [LIKELY].
- **What happens:** Each builder knows its own suppliers; new suppliers with 1–3 orders look the same as proven ones; nobody can compare across builders.
- **Who feels it:** Developers choosing suppliers; honest suppliers who cannot prove reliability; banks scoring them.
- **Possible solution:** An Empirical Bayes score that shrinks small samples toward the group average and shows a confidence level, portable across builders with consent.
- **Hardware option:** None.
- **First metric:** Share of active suppliers with a score and its confidence.

### Context, not a target
Foreign railcars are reported to displace the local fleet (S17). This matters for rail carriers; SitePulse's first customers are road deliveries to construction sites.
