# Delivery evidence implementation status

Updated 3 November 2026. This records local software verification, not a customer deployment or completed field pilot.
The authorised implementation follows the [product plan](plans/delivery-evidence-reshape.md). The original research remains a dated source snapshot.

## Delivered software

| Backlog | Implementation | Remaining release evidence |
|---|---|---|
| E1 | Alembic baseline and additive receiving migrations; populated legacy upgrade; SQLite and PostgreSQL recovery tooling | Rehearse against the actual customer's backup before upgrading that installation |
| E2 | Named coordinator/receiver/viewer credentials, site scope, revocation, plans independent of predictions and exact totals across partial receipts | Named site owner, account handover and access review |
| E3 | Arrival/quantity/condition, optional location, private media, partial acceptance, append-only revisions, concurrent idempotent retries, audit events | Validate actual receiver workflow and evidence policy |
| E4 | Russian desktop/phone receiving UI at `/receive`; reference/QR fallback; confirmation/disputes, exceptions, ZIP/JSON export and print, explicit plan closure | Physical pilot-phone and user acceptance checks |
| E5 | Offline shell, IndexedDB draft/media persistence, interrupted-sync retry, visible conflicts/storage errors, draft export/import | Browser storage eviction and actual device/network conditions remain field checks; local storage is not a backup guarantee |
| E6 | Separate customer Compose configuration, Caddy TLS configuration, no demo seeding or public legacy APIs, DB/media backup/restore scripts, operator runbook | Actual Kazakhstan/on-prem host, DNS/TLS, retention agreement, restore rehearsal and owner sign-off; Docker stack has not been launched locally |
| E7 | Optional manual document entry and exact line matching against accepted current revisions, split receipts and multiple-document review | Accountant's permitted samples, allocation decisions and handling-time comparison |
| E8 | Optional revision-specific read-only evidence grants, consent reference, expiry/revocation, redaction and access logs | Named recipient, approved fields/consent and evaluation of a real authorised packet |
| E9 | Optional physical-resource requests and coordinator approval/move/cancel; overlap locking, in-app notifications, supplier arrival history with intervals | Repeated operational demand and field data; no outbound messaging or autonomous booking |
| V0 / V1 | Pilot protocol, blank collection templates and coordinator coverage-report UI/export prepared | Interviews, host agreement, independent arrivals register, 30-day pilot and commercial decision are **not performed** |

E7–E9 are **disabled by default**. Their software can be rehearsed with synthetic data; customer use still depends on the roadmap gates. No bank integration, payment release, state-system submission, hardware pilot or customer traction is claimed.

## Verification evidence

Local checks on Python 3.12 and PostgreSQL 16.15:

- **263 passed, 1 skipped** in the complete Python suite (the opt-in PostgreSQL migration test runs separately); legacy signed ingest, scheduling, layering and claim guards remain included.
- Receiving suite on both SQLite and PostgreSQL: **28 tests passed on each database**, including simultaneous duplicate receipts/corrections, cross-site media denial, credential revocation, revision/decision conflicts and simultaneous overlapping slot approvals.
- **25 PostgreSQL receiving/operations checks passed in the combined run**, plus the added concurrent document-retry regression passed separately. This included a real dump/restore test for a receipt, its revision and exact attachment bytes. The legacy migration canary and metadata comparison also passed. SQLite restore/tamper/overwrite guards are covered in the suite.
- Chromium, Firefox and WebKit browser → API → database rehearsals passed: login, resource approval, document entry, denied GPS, injected storage-quota failure without clearing the form, offline capture/reload, interrupted file upload, partial acceptance, corrections, draft backup/restore, credential-free caches and revoked access.
- Browser screenshots and reports are generated into ignored `test-results/receiving/` (Firefox/WebKit have their own subdirectories); run `python -m scripts.verify_receiving_browser` to reproduce. All rehearsal records are synthetic, including tests that exercise `REAL` eligibility branches.
- Caddy validated the customer TLS/proxy configuration locally; Compose and CI YAML parsed. Actual certificates, container startup and host networking remain deployment checks.
- CI configuration adds browser artifacts and PostgreSQL migration/recovery checks. Remote CI has not been run by this local session.

These checks do not establish legal validity, independent physical-delivery proof, a production SLA, measured savings or real-world model performance.

Core implementation commit: `6ec046b`. Deployment/recovery tooling commit: `a77474a`.

## Continuation: coordinator workflow and browser recovery

- Added plan/actual cards with observed, accepted and remaining quantities across current revisions. Confirmed acceptance alone contributes to fulfilment. Units/materials stay separate; plan closure is an explicit coordinator decision.
- Correcting a receipt retains its plan even when that plan is closed or outside the recent 200-plan list. Closed plans remain accessible from Today. Correcting a load removes superseded acceptance from plan totals.
- Added the coordinator's pilot-report screen with an independent denominator/register reference, explicit period, SIM exclusion and a downloadable report containing the site and calculation time. This is a reporting tool, not evidence that the pilot happened.
- WebKit rejected IndexedDB Blob/File persistence in the rehearsal. New drafts store ArrayBuffer photo bytes; old v1 Blob drafts remain supported and were exercised in Chromium. Optional browser persistence permission failure or an unanswered prompt no longer delays acknowledgement of a successfully saved draft.
- Switching person/site clears prior reports, capture fields and visible drafts. Cross-browser verification is now configured in CI for Chromium, Firefox and WebKit; local status is stated above, remote CI remains unrun.

## Continuation: complete evidence exports and atomic restore

- A site-scoped ZIP contains the receipt JSON, every recorded revision's attachment bytes, a checksum manifest and handling notes. The export holds the receipt lock while taking its snapshot and rejects stored file corruption before returning anything. Superseded evidence is included, not overwritten by the current version.
- The standalone `scripts/verify_receipt_bundle.py` checks checksums, file lists, revision/attachment identities and paths without extracting archive content. Verification establishes internal consistency only, not a trusted author, legal validity or physical delivery.
- Backup restore now validates the whole input, detects changed content under an existing operation ID, and commits all new drafts in one IndexedDB transaction. Storage failures roll the entire batch back. Identical drafts retain their current sync progress. Export normalises recognised media types for compatibility with older Blob-based drafts.
- API checks cover full revision/media inclusion, viewer access, cross-site denial, archive tampering, corrupted stored media and export limits. Browser rehearsals additionally download/verify a two-revision ZIP and inject malformed backups, changed files and a mid-restore storage failure.

## Operating limits

The receiver credential is a revocable per-person bearer key held in browser memory. It is not SSO/MFA. Offline drafts and media are stored on the device; use a controlled device/browser profile. Cached plans and unsent drafts survive reload; signing out removes cached profile/plans but keeps recoverable drafts. A revoked key cannot sync them; preserve a private draft backup for an operator-led recovery.

Files are stored transactionally in the database, capped at six files of 5 MiB each per revision. A full ZIP export is capped at 100 MiB / 1000 attachments; JSON and individual downloads remain available for larger histories. Backups include them. This simplifies the one-site pilot but is not a large-volume object-storage architecture. A digest detects byte changes when compared with a trusted copy; a database administrator could alter both data and hashes. Attestations identify the app account, not an independently verified identity.

Plans show the most recent 200 entries; receipts load in pages. Supplier history, reconciliation and metrics are designed for a bounded one-site pilot and scan site records. The independent arrivals denominator is supplied by the coordinator and must be checked outside the app. Receipt IDs prevent transport duplicates; they do not prove two separately entered records represent different physical trucks.

The legacy date-only signed gate intake remains a separate contract. It does not silently turn prediction logs into receiving attestations. Optional document entry is manual; CSV/state-system connectors and driver acknowledgement are future extensions. QR scanning depends on browser support; manual reference entry is always available.

## Next real-world action

Use the [receiving runbook](RECEIVING_RUNBOOK.md), [pilot proposal](PILOT_PROPOSAL.md) and [field checklist](pilot/field-checklist.md) to select and prepare one host. Record the actual decisions and observations. Do not enable customer intake until the host/device/access/recovery checklist is completed.
