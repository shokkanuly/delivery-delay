# 03 · Fintech problems

Tags: **[CONFIRMED]**, **[LIKELY]**, **[UNVERIFIED]**. Source codes point to `08-sources.md`. Rule of thumb: do not become a lender or a bank. Be the data partner of licensed institutions.

## Money and credit

### F02 · Costly working capital
- **Status:** [CONFIRMED]. The National Bank cut the base rate to 15.75% on 23 October 2026 (it was 18% earlier in the year); inflation was 9.3% in September; average tenge corporate loans were above 22% in spring and summer 2026 (S9, S10).
- **What happens:** A supplier waits weeks for payment and borrows at high rates meanwhile.
- **Who feels it:** Material suppliers, subcontractors.
- **Possible solution:** Verified delivery shortens the time until the invoice is accepted and funded by a partner bank, MFO or factor. You earn a data fee, not interest.
- **Hardware option:** None.
- **First metric:** Days from delivery to payment, before and after.

### F05 · Factoring anchored to contracts, not site delivery
- **Status:** [CONFIRMED] for the product description, [LIKELY] for the gap. Halyk offers "digital factoring" for suppliers on government procurement contracts, financing the receivable (S11). BCC advertises factoring from 8.5% (S11). The Association of Financiers argues factoring should grow (S11).
- **What happens:** Banks assess the contract, the buyer and the receivable. Whether the goods physically arrived on time is not something these products are reported to verify.
- **Who feels it:** Banks (risk), suppliers (limits and price).
- **Possible solution:** Offer the bank a delivery-evidence feed. Test in interviews first (see `05-delivery-vs-banks.md`).
- **First metric:** Number of banks willing to test the feed on real invoices.

### F09 · Licensing and AML burden for lenders
- **Status:** [LIKELY]. Lending, factoring and payments need licences and capital.
- **Possible solution:** Partner with a licensed bank, MFO or factor; use the AIFC FinTech Lab sandbox if you ever need regulated testing (S24).
- **First metric:** Signed partner agreements.

## Trust and documents

### F01 · Fake or backdated delivery documents behind financing requests
- **Status:** [LIKELY]. The tax authority's Virtual Warehouse regime was extended to building materials to fight the shadow economy (S5). Whether banks actually see phantom factoring in construction is not confirmed.
- **What happens:** A signed paper waybill can be late, wrong or backdated. A financier cannot tell.
- **Possible solution:** A Verified Delivery Certificate (VDC): gate time, photo, quantity, receiver sign-off, linked ЭСФ/СНТ numbers, hash in an append-only log, FEED (live) versus SIM (test) tags.
- **First metric:** Mismatches caught per 100 invoices.

### F04 · Manual 1C, ЭСФ and bank reconciliation
- **Status:** [LIKELY]. The buyer's СНТ confirmation is a separate accounting action with a deadline (sources give 10 calendar days, 20 working days or 20 calendar days depending on version and transport mode, so read the current rule; S6).
- **What happens:** Accountants match deliveries, invoices and payments by hand; errors go back and forth ("data differ in row 2").
- **Possible solution:** Automatic match of the delivery event to ЭСФ/СНТ numbers and payment lines; exceptions list.
- **First metric:** Hours per month spent on reconciliation.

### F03 · No supplier track record for SMEs
- **Status:** [LIKELY].
- **Possible solution:** Empirical Bayes supplier score with a confidence level, plus a bank API (consent-based).
- **First metric:** Suppliers with a usable score.

### F06 · Milestone and payment-release disputes
- **Status:** [LIKELY]. Baiterek planned about 2.41 trillion tenge of housing support in 2026 (S12). Since January 2026 a Kazreestre service checks non-cash payments on registered shared-construction contracts, and engineering companies monitor progress, use of buyers' money and volumes of work (S13, S14).
- **What happens:** Money control exists at the contract and payment level. Delivery of materials to the site is a link in the middle that is not described in these sources.
- **Possible solution:** Delivery evidence for technical supervisors and funders.
- **First metric:** Disputes closed per week.

## Infrastructure and risk

### F08 · Interbank QR rails (late, now connected)
- **Status:** [CONFIRMED]. The President criticised the biggest banks in March 2026 for delays joining the interbank QR system; all banks were later reported connected (S15).
- **Possible solution:** Enables pay-on-delivery triggers later.

### F07 · Consumer fraud and dropper schemes
- **Status:** [CONFIRMED], out of scope. The National Bank's Antifraud Center logged over 60,000 incidents in its first 10 months, mostly phone fraud (22%) and dropper cards (19%); banks stopped more than 49 billion tenge of fraudulent operations from early 2025 to March 2026; only about 26% of losses were recovered (S16).
- **Why it matters for you:** Trust in digital finance is fragile. Keep identity and consent flows lean and transparent.
