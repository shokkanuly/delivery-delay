# Receiving deployment on Vercel

The user selected Vercel on 3 November 2026. Use the project's provided HTTPS
`*.vercel.app` domain; purchasing a custom domain is not required. The existing
public Railway URL is the historical audit demo, not evidence that the receiving
branch has been deployed.

## Prepared application

- `vercel_app.py` exports the receiving-only FastAPI application. It includes the
  receiving UI, scoped API and optional extension routes, without seeding data or
  loading the historical model/analyst application.
- `pyproject.toml` and `uv.lock` define the smaller Python 3.12 runtime. Vercel
  uploads exclude the full `requirements.txt` and private/local files via
  `.vercelignore`. The original Docker and local audit setup still uses
  `requirements.txt`.
- `vercel.json` selects FastAPI and a 60-second function limit. Static CDN promotion
  is explicitly disabled so the customer-route boundary also guards static files.
- Vercel uses persistent PostgreSQL supplied in `DATABASE_URL`; SQLite is rejected
  at startup. Connections close after use with `NullPool`. Migrations retain the
  existing PostgreSQL advisory lock.
- Vercel limits individual files and whole ZIP downloads to **4 MiB**. The login
  profile advertises the limit; capture validates it and unsendable old drafts stay
  recoverable. Larger histories use JSON plus individual files, or the operator's
  full container installation for a complete ZIP. Existing files over the hosted
  limit must be recovered through that installation, not deleted or resized in place.

These settings follow the official [FastAPI deployment guide](https://vercel.com/docs/frameworks/backend/fastapi),
[Python runtime](https://vercel.com/docs/functions/runtimes/python) and
[function payload limits](https://vercel.com/docs/functions/limitations).

## Deployment sequence

1. Authorize the Vercel connection for the intended team. Resolve the existing
   project by Git repository before creating a new project; do not replace an
   unrelated deployment. Record the team/project, current production deployment,
   branch and exact commit in the private operator log.
2. Select a dedicated persistent PostgreSQL database and approved data scope.
   Inspect whether it is empty. If populated, back it up and rehearse the additive
   migration against an isolated restore before deployment. Never use a temporary
   local SQLite database or an unrelated project's database.
3. Configure secrets privately in Vercel's project settings. Do not paste them in
   chat, commit them, or include them in build artifacts. Required values:

   | Variable | Meaning |
   |---|---|
   | `DATABASE_URL` | Dedicated PostgreSQL connection URL, with provider-required TLS |
   | `SITEPULSE_ADMIN_KEY` | Unique random private operator key, at least 32 characters |
   | `SITEPULSE_MODE` | `customer` |
   | `SITEPULSE_ENABLE_RECONCILIATION` | `0` |
   | `SITEPULSE_ENABLE_PARTNER_SHARING` | `0` |
   | `SITEPULSE_ENABLE_OPERATIONS` | `0` |
   | `SITEPULSE_CORS_ORIGINS` | Empty for the same-origin receiving UI |

   Vercel supplies `VERCEL=1` automatically. Keep preview and production databases
   and operator keys separate. No database service or paid upgrade is provisioned
   by the repository configuration.
4. Build the reviewed commit with the FastAPI preset and repository root. Ensure
   no stale dashboard Build/Install/Output override replaces the checked-in
   configuration. Inspect logs for the receiving dependencies and successful
   startup. A green local test is not a successful Vercel deployment.
5. Before assigning production traffic, verify the exact deployment's `/readyz`,
   root/receiving UI, guarded legacy routes, named provisioning/login, receipt and
   photo capture, export, fresh-session persistence, revocation and offline reload.
   Rehearse near-limit uploads and ZIP overflow on the hosted endpoint as well.
   Use only SIM data until the field-readiness record is complete.
6. Promote the tested deployment to the project's Vercel-provided domain and repeat
   the public-domain checks. Record the deployment ID, URL, commit and results.
   Preserve the prior deployment for rollback; restoring application code does
   not roll back or replace the database.

The operator can provision named access using the authenticated receiving API;
each credential is shown once and transferred privately. Follow the
[runbook](RECEIVING_RUNBOOK.md) for account handover, backups and revocation.

## Current boundary

The Vercel configuration and local runtime checks are prepared. Team access was
denied by the connector and authorization was requested; the existing target,
database and remote build have not yet been verified. No successful Vercel
deployment or public receiving URL is claimed by this record. See the
[remaining tasks](REMAINING_TASKS.md) for the concrete completion evidence.
