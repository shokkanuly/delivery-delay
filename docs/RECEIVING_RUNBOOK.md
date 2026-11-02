# Receiving operator runbook

The receiving application is independent of model training. Use Python 3.11/3.12 and the existing requirements. A customer installation is a separate database and deployment; the public historical demo remains synthetic-only.

## Local synthetic rehearsal

From the repository root after installing requirements:

```bash
mkdir -p var/receiving
export DATABASE_URL=sqlite:///./var/receiving/preview.db
export SITEPULSE_MODE=customer
python -m scripts.receiving_demo
python -m uvicorn api.main:app --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/receive`. The demo helper creates three clearly labelled SIM plans and writes a private named credential to `var/receiving/preview-access.json` (mode 0600). Read that local file and enter the credential at login. It is not committed or printed in logs. The helper will not overwrite an existing credential file. Customer mode disables legacy APIs and automatic synthetic seeding; the explicit demo helper is only for a disposable local rehearsal.

Before updating the application, sync or export local drafts, then close receiving tabs and reopen them so the new versioned offline shell can activate. Do not clear browser storage to update.

The static legacy console links to `/receive`. In customer mode the root URL opens receiving. `/readyz` checks database connectivity without requiring a trained model. Credentials stay in memory and must be re-entered after a reload. Drafts and media remain in the browser's IndexedDB. New media are stored as binary bytes for browser compatibility; existing Blob-based drafts remain readable. Optional storage-persistence prompts do not block acknowledgement after a successful local save.

For synthetic extension rehearsals, set the flags before starting:

```bash
export SITEPULSE_ENABLE_RECONCILIATION=1
export SITEPULSE_ENABLE_PARTNER_SHARING=1
export SITEPULSE_ENABLE_OPERATIONS=1
```

Keep them unset/0 for the initial customer receiving pilot. In-app notifications do not send email, SMS or messenger messages.

## Provision and revoke a person

Use the customer's DATABASE_URL on the authorised operator machine:

```bash
python -m scripts.receiving_admin --site-name 'Agreed site' --name 'Named coordinator' --role coordinator --output var/receiving/coordinator.json
python -m scripts.receiving_admin --site-id ACTUAL_SITE_UUID --name 'Named receiver' --role receiver --output var/receiving/receiver.json
```

Transfer each credential privately to its named user. Never share the operator key with a receiver. A person belongs to one site; provision separate access when appropriate. Available roles: coordinator (plans, review, documents/grants/slots), receiver (capture/attestation and own corrections), viewer (read only). A coordinator can correct/review other records at their site. Any authorised receiver can confirm a site receipt; record the actual receiving person's account.

Provisioning is also available via `POST /receiving/sites` and `POST /receiving/sites/{site_id}/actors`, using the server's `X-API-Key`. Revoke with `POST /receiving/actors/{actor_id}/revoke` using that same operator authentication. No public account registration exists. A new key means a newly provisioned actor; preserve old actor IDs for historical attribution. Revoke the old actor and arrange operator-led handling of any unsent drafts before replacing access. Never impersonate an old receiver to resubmit evidence without recording that recovery decision.

## Customer host preparation

Choose the agreed Kazakhstan/on-prem host, domain, operator and backup location first. Copy `.env.customer.example` to `.env.customer`, generate unique credentials, URL-encode the database password in DATABASE_URL and set the actual domain. Do not use the example secrets. Allow ports 80/443 for Caddy and keep Postgres unexposed.

```bash
docker compose --env-file .env.customer -f docker-compose.customer.yml config -q
docker compose --env-file .env.customer -f docker-compose.customer.yml up -d --build
```

This configuration starts Postgres, the receiving API and Caddy. The API migrates on startup under a PostgreSQL advisory lock; it does not seed/train a model. Caddy's certificate issuance needs correct DNS and network access. Validate the real HTTPS URL, `/readyz`, named login, revocation, denied legacy routes, offline reload and recovery before allowing real intake. The configuration was prepared locally; no customer stack or TLS endpoint was deployed by this implementation session.

The API container does not contain PostgreSQL CLI backup tools. Run the Python backup helper from an authorised operator environment with `pg_dump`/`pg_restore` on PATH and secure DB connectivity, or use the database container commands below. Do not expose the database publicly merely to run backups.

## Backup and restore

Back up before any migration and at the frequency agreed with the host. The database contains private attachment bytes, actor hashes and audit records; protect the backup and its manifest equally. Use encrypted storage at rest and agreed access/retention on the host. File permissions alone are not encryption. Set recovery-point/recovery-time objectives with the site owner; no defaults are promised.

For SQLite, or PostgreSQL reachable securely by the operator (matching or newer-major backup clients):

```bash
python -m scripts.receiving_backup backup var/backups/receiving-YYYYMMDD.dump
# Point DATABASE_URL at a NEW SQLite file or an EMPTY PostgreSQL target.
python -m scripts.receiving_backup restore var/backups/receiving-YYYYMMDD.dump
```

The helper never overwrites an existing backup or nonempty target, verifies SHA-256 before restore, and writes a 0600 manifest beside the dump. Use `.db` as the filename for SQLite if preferred; the manifest records its actual format. SQLite uses its consistent backup API. PostgreSQL uses a custom-format database dump. Test restoration into an isolated target, then inspect receipt history and download a known attachment to compare its digest.

For the supplied container stack, an operator can keep DB access internal:

```bash
mkdir -p var/backups
umask 077
# Choose a new filename for each backup; do not overwrite an earlier backup.
set -C
docker compose --env-file .env.customer -f docker-compose.customer.yml exec -T db pg_dump -U sitepulse -d sitepulse -Fc > var/backups/customer-YYYYMMDD.dump
shasum -a 256 var/backups/customer-YYYYMMDD.dump > var/backups/customer-YYYYMMDD.dump.sha256
set +C
# Verify the digest, create a NEW rehearsal database, then restore there.
shasum -a 256 -c var/backups/customer-YYYYMMDD.dump.sha256
docker compose --env-file .env.customer -f docker-compose.customer.yml exec -T db createdb -U sitepulse receiving_restore_YYYYMMDD
docker compose --env-file .env.customer -f docker-compose.customer.yml exec -T db pg_restore -U sitepulse --no-owner --no-acl --exit-on-error -d receiving_restore_YYYYMMDD < var/backups/customer-YYYYMMDD.dump
```

The container dump's `.sha256` sidecar is a separate operator workflow, not the Python helper's JSON manifest. Check every command's exit code. The container workflow needs rehearsal on the actual host; local automated recovery used the Python helper with PostgreSQL 16.15.

Prefer forward fixes. Never downgrade receiving migrations on a live database: restoring a pre-change backup into a separate target is the recovery path. Freeze writes and preserve the current DB before deciding to switch targets; reconcile records made after the backup so a rollback does not silently lose arrivals. Preserve or rotate credentials according to the incident, and keep access revoked during investigation.

## Offline and evidence workflow

1. Log in online on the agreed phone/browser profile and wait for the app to load. Confirm offline reload before field use.
2. Select a plan or enter an unplanned reference. Verify the quantities copied from a plan; they are editable, not measured values. Record condition, time source and optional GPS. Camera/GPS denial must not block manual capture.
3. Save on device. Keep the page/form open if storage reports failure. A saved local draft is not yet on the server. Export private draft backups during a prolonged outage.
4. Send drafts after reconnecting and signing in. Interrupted file uploads retry with stable IDs/hashes. A conflict remains visible; inspect the current server revision, then make a reasoned correction. Never clear browser storage to “fix” an unsent record.
5. Open the receipt, inspect files and confirm accepted quantities or dispute. A correction preserves the previous record and needs current files and a new confirmation. Partial acceptance remains a discrepancy. Closing a plan is a separate coordinator decision.
6. Open «План / факт» to inspect totals across partial loads. Only accepted quantities on currently confirmed revisions count toward the plan. Different units/materials remain separate. Use the coordinator decision form to complete or cancel the plan with a reason; quantity equality does not close it automatically. Closed plans remain in the Today archive, and later corrections preserve the plan association.
7. Export the packet/print view and download attachments when needed. The JSON includes hashes and attachment metadata, not embedded photo bytes. Export is access-controlled and audited. Keep downloaded files private.

Browsers may evict local storage. The app does not promise survival after device loss, user deletion or browser eviction. A backup file is limited to 100 records/100 MiB; use «Скачать копию» on individual rows for a larger queue. Draft backup import preserves operation IDs and media, and only imports into the same actor/site profile. Revocation blocks upload while leaving drafts locally recoverable. Device timezone/clock and weak connectivity can affect observed time; server receipt time and clock warnings remain separate.

## Coverage and optional sharing

The coordinator can open «Отчёт пилота», select a period, supply the independently observed arrival count/register reference, and download the report. Inputs use the device timezone; the request carries explicit offsets. The report includes the site ID and calculation time and describes the current revision/confirmation state. The same calculation is available via API.

`GET /receiving/metrics` requires coordinator auth, timezone-aware `start`/`end` (exclusive end, at most 93 days), `eligible_arrivals` and `register_reference`. Supply the independent gate register, reconcile duplicate physical arrivals, and include unrecorded arrivals in the denominator. SIM records are excluded. The endpoint reports recorded and complete-confirmed coverage; it does not measure capture duration or savings. Record burden and discrepancy outcomes separately in the pilot register.

Document reconciliation compares exact line IDs/materials/units with accepted quantities on current confirmed revisions. Multiple documents for one plan require manual allocation review. A match is not automatic accounting acceptance. External sharing additionally requires its feature flag, a complete confirmed REAL receipt, named recipient/purpose/consent reference and expiry within 30 days. The returned secret is used only in `X-Evidence-Key`, never a URL. A correction, revocation, expiry or revoked issuer invalidates access. Shared output excludes photos, GPS, names, notes and document references. A recipient still needs to assess usefulness and lawful scope before real sharing.

## Verification and retention handoff

```bash
python -m pytest -q
python -m scripts.build_demo_report --check
pip install -r requirements-dev.txt
python -m playwright install chromium firefox webkit
python -m scripts.verify_receiving_browser --browser chromium
python -m scripts.verify_receiving_browser --browser firefox
python -m scripts.verify_receiving_browser --browser webkit
```

Browser runs use disposable synthetic databases and isolated profiles. On macOS the Firefox test additionally uses a fresh app-data directory, separate from personal Firefox state ([upstream issue](https://github.com/microsoft/playwright/issues/42768)). It does not change system permissions or personal browser settings. Playwright WebKit is engine coverage, not physical iPhone/Safari acceptance.

PostgreSQL test opt-ins: `SITEPULSE_TEST_RECEIVING_POSTGRES_URL` allows disposable random schemas; `SITEPULSE_TEST_POSTGRES_URL` must be an empty migration-rehearsal DB; `SITEPULSE_TEST_RESTORE_URL` must be an empty restore DB. Never point them at customer data. CI declares isolated services for these checks.

Before field intake, agree retention for server evidence, browser drafts, exports and backups, including who can authorise deletion and exceptions for disputed records. No automatic evidence purge is enabled. After policy approval, carry out documented operator maintenance with a verified backup and audit of what was removed. Test on the pilot phone using the [field checklist](pilot/field-checklist.md) and record actual results in the pilot evidence log.
