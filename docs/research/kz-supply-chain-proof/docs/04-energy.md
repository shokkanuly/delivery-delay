# 04 · Energy problems

Tags: **[CONFIRMED]**, **[LIKELY]**, **[UNVERIFIED]**. Energy is the hardest area for a small team to enter. Buyers are state utilities and large integrators. The realistic entry is measurement on the construction and industrial sites you already serve.

## Supply and grid

### E01 · Electricity deficit
- **Status:** [CONFIRMED]. The government expects to cover demand by the end of Q1 2027 and reach a more stable surplus by 2029; about 2.6 GW of new capacity is planned in 2026. On 28 October 2026 the President again called current output of 123 billion kWh a year insufficient (S18).
- **Who feels it:** Industry, developers, households.
- **Possible solution:** Site and plant energy visibility, so users know their peaks and waste.
- **First metric:** kWh per site per week.

### E02 · Worn grid and outages
- **Status:** [CONFIRMED]. Wear was about 53% at power plants, 50% on heat networks and 66.2% on electric grids; 384 billion tenge was allocated for plant repairs in 2026, and the modernization plan covers 10,490 km of electric grids (626.8 billion tenge in total) (S19). Regional imbalances remain even after the national deficit closes (S18).
- **Possible solution:** A power-quality logger at the site gate or plant: outages, voltage sags, timestamps. Useful as evidence in disputes and for planning generators.
- **Hardware option:** ESP32 with a voltage sensor and a battery, MQTT or local storage.
- **First metric:** Outage and sag events logged per month.

### E03 · Heat-network wear and winter heating cost
- **Status:** [CONFIRMED] for network wear; [LIKELY] for the construction angle.
- **What happens:** Winter construction needs heating and curing. Energy used per pour is rarely measured.
- **Possible solution:** Track kWh or fuel per pour; temperature loggers in curing concrete (needs calibration and checking against construction standards).
- **First metric:** kWh per cubic metre cured.

## Data and measurement

### E04 · Thin metering
- **Status:** [CONFIRMED]. Automated metering has low penetration; about 4 million smart meters are planned (S20).
- **Possible solution:** Low-cost sub-metering on pumps, cranes and generators (clamp-on current sensor plus ESP32) with an open API.
- **First metric:** Assets metered.

### E05 · No digital expenditure accounting in tariff approval
- **Status:** [CONFIRMED]. The ministry names this gap (S20).
- **Possible solution:** A per-asset energy ledger. This is B2G work for later, not for your first year.

### E09 · Sector cybersecurity and air-gapped sites
- **Status:** [CONFIRMED] that a sector cybersecurity centre and an infocommunication operator are due by the end of 2026 (S20). [LIKELY] that many industrial buyers block software that calls external services.
- **Possible solution:** Deployment on an offline or on-prem machine, no external calls, auditable.

## Opportunities specific to a delivery platform

### E06 · No energy or CO₂ per delivery
- **Status:** [LIKELY].
- **Possible solution:** kWh, fuel and CO₂ per delivery from truck idle time at the gate, pump power and generator fuel.
- **Hardware option:** Clamp-on current sensor, fuel-level sensor.
- **First metric:** Share of assets reporting CO₂ per delivery.

### E07 · Pump and equipment waste or wear
- **Status:** [LIKELY].
- **Possible solution:** Anomaly detection (for example Isolation Forest) and an energy-aware pump controller. A research project on AI pump control can feed this.
- **First metric:** kWh saved per pump.

### E08 · ESG and green-finance evidence
- **Status:** [LIKELY].
- **Possible solution:** An auditable, append-only ledger where every row is tagged FEED (live sensor) or SIM (simulation). That distinction is what an auditor or lender will ask about first.
- **First metric:** Reports produced from real data.
