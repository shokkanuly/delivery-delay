# Remaining release and field work

Updated 3 November 2026. Core receiving software and optional disabled extensions
are implemented. This list separates repeatable engineering checks from actions
that require the actual host, users, records or passage of time.

| Task | Status / next action | Completion evidence |
|---|---|---|
| Full customer-container rehearsal | Completed in [CI run 41614280620](https://github.com/shokkanuly/delivery-delay/actions/runs/41614280620) | TLS client verification, capture/export, container recreation, credential revocation, exact media restoration and cleanup passed |
| Vercel runtime preparation | Receiving-only entrypoint, locked dependencies, persistent-DB startup guard, scoped static routes and hosted file limits implemented | Local API tests and browser flow; CI verifies the minimal runtime in all three engines |
| Vercel team/project access | Awaiting team authorization requested through the connector | Intended team and existing repository-linked project accessible |
| Persistent hosted database | Not yet verified; inspect project settings after access is available | Dedicated PostgreSQL, approved data scope, private credentials; no unrelated database reused |
| Live receiving deployment | User authorized Vercel; pending access and database | Exact tested deployment reachable on its provided HTTPS domain; persistence and file-limit checks passed |
| PR integration | [Draft PR #7](https://github.com/shokkanuly/delivery-delay/pull/7) contains the implementation | Final review and deliberate merge decision; deployment need not silently merge the PR |
| Host/user handover | Pilot site and named owner/receiver not supplied | Scoped accounts privately delivered; receiver demonstrates capture, confirmation, export and revocation |
| Real backup/upgrade rehearsal | Synthetic SQLite/PostgreSQL and container recovery passed; actual installation still open | Actual host's backup restored in isolation, known evidence hashes checked and recovery objectives recorded |
| Physical-phone acceptance | Browser-engine automation passed; real phones still open | Phone model/browser and actual observations entered in the field checklist, including restart, eviction/storage limits and weak connectivity |
| Discovery and pilot preparation | Templates prepared; interviews and site observations not performed | At least six relevant interviews, one host, material family, access/retention decisions and independent arrivals register |
| 30-day field pilot | Cannot be completed without a host and 30 days of observations | Independent coverage, capture burden, evidence gaps, sync failures, discrepancies and buyer decision recorded |
| E7 document reconciliation | Software disabled pending the accountant's demonstrated need | Permitted document samples and measured matching workflow |
| E8 external evidence sharing | Software disabled pending a named recipient and agreed scope | Consent/fields and an actual authorized packet evaluated |
| E9 resources/slots | Software disabled pending repeated coordination demand | Site approves the workflow using real queue/resource observations |

No software run substitutes for an interview, physical-phone observation,
recipient consent or completed pilot. Record actual evidence privately with the
host; do not publish names, credentials, receipts or customer backups in this repo.

Use [Vercel deployment](VERCEL_DEPLOYMENT.md), the [operator runbook](RECEIVING_RUNBOOK.md),
[field checklist](pilot/field-checklist.md) and [pilot protocol](PILOT_PROPOSAL.md).
