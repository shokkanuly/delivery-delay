# Research → product decisions

Updated 20 October 2026. This is a synthesis of the founder-provided research notes and
`SitePulse_IdeaMiners_2026.pdf`, not independent customer validation or an official judging rubric.
The original private attachments are not copied into this public repository.

| Research finding / recommendation | Product decision | What can be checked |
|---|---|---|
| Plausible pain, unproven demand; holding-wide scope is too broad | Start with one contractor and one site | README, PRD and pilot proposal use the same scope. |
| Synthetic model lift over a supplier average is modest | Sell the scorecard first; compare the model to the baseline on each history | Chronological audit; no model bands if it fails to beat the baseline. |
| 1C is the existing record system | Read CSV exports rather than replace the ERP | Russian headers, cp1251, quality warnings and downloadable fixture. |
| Judges need something they can inspect | Public sample with no registration or shared admin credential | Report JSON is generated from the same downloadable CSV; its source hash is included. |
| Willingness to pay and site counts are not established | Describe tenge prices as founder hypotheses; do not publish an unsupported TAM | One-site pilot with explicit decision criteria, no forecast presented as traction. |
| Existing booking tools are credible alternatives | Name Voyage Control and investigate local substitutes | No “no competitors” or unsupported feature-absence claim. |
| Local customer deployment and a measured pilot are prerequisites | Railway is synthetic only; Kazakhstan/on-prem hosting remains a pilot requirement | Current roadmap and deployment boundaries. |

## What is evidence, and what is still a hypothesis?

**Evidence in this repository:** working import/audit/exposure flows, tests, synthetic examples,
algorithmic constraints and code that records predictions and arrivals.

**Founder hypotheses:** procurement staff will use the scorecard, the initial contractor segment,
150,000–300,000 ₸ per active site/month, and adoption through a free audit and one-site pilot.

**Not established:** measured crane-idle reduction, customer willingness to pay, local market size,
completed interviews, customer audit outcomes, a signed pilot, or a production SLA.
Do not turn the 2022 media delay statistic, developer residential-complex counts, or total
construction turnover into a delivery-delay rate or addressable site count.

## External reference checked for this revision

[Voyage Control's official product site](https://www.voyagecontrol.com/) describes procurement,
delivery booking, cranes/hoists and supplier reporting. It demonstrates a substantial adjacent
product category. We do not claim that it lacks risk features, integrations or customers in a
particular country; those comparisons have not been established.

The supplied competition context is useful for a concise business demo. The public Idea Miners
page could not be retrieved during this revision; we have not independently verified judge
names, scoring weights or a promised prize. No such facts are used as product evidence.

## Next evidence to collect

1. Record interviews with procurement/site staff in [CUSTDEV_LOG.md](CUSTDEV_LOG.md).
2. Obtain permission to process a contractor export in its Kazakhstan/on-prem deployment.
3. Deliver one audit and record whether it changes a supplier decision.
4. Agree one site's 30-day pilot, arrival coverage and usage targets before starting.
5. Measure live accuracy only after enough resolved deliveries; separately measure operational
   effect and willingness to pay. A synthetic benchmark or letter of intent cannot establish either.
