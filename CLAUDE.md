# CLAUDE.md — SitePulse (repo: shokkanuly/delivery-delay)

SitePulse now includes delivery receiving at `/receive`: plan → record arrival and quantity →
named confirmation/dispute → review and export. The historical-audit prototype and signed arrival/ML
contracts remain. Customer mode serves only the receiving surface and disables demo seeding.
Bundled data and implementation rehearsals are synthetic; no completed customer pilot is established.

**Current implementation:** `docs/IMPLEMENTATION_STATUS.md`, `docs/RECEIVING_RUNBOOK.md`.
**Product scope and remaining gates:** `docs/plans/delivery-evidence-reshape.md`, `docs/PRD.md`, `ROADMAP.md`.
The user authorised full implementation after the planning pass. Alembic, the offline IndexedDB/service-worker
pattern, Playwright verification and Caddy customer-stack configuration were selected within that scope.
E7–E9 remain disabled by default pending their real-world gates. Read the status before assuming deployment
or field validation is complete. October's `docs/plans/mvp-reshape.md` remains historical.

## Commands
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest
python -m pytest -q                        # all tests (must stay green; 155 on 2026-10-19)
python -m pytest -q tests/test_layering.py # layering rule only
./start.sh                                 # trains if needed, API :8000 (console at /), Streamlit :8501
python -m db.seed data/synthetic/delay_prediction.csv && python -m ml.train data/synthetic/delay_prediction.csv
docker compose up --build                  # Postgres + seed/train + API + dashboard
```

## Architecture rules (do not break)
1. **Calls only go down.** `ml/`, `engines/`, `business/` are pure Python: no `fastapi`, `starlette`, `streamlit`,
   `requests`, `api` or `dashboard` imports (`tests/test_layering.py` fails otherwise).
2. **One router per domain** in `api/routers/<domain>.py`; `api/main.py` only wires routers. Pydantic models live in
   `api/schemas.py`.
3. **One schema of record:** `db/models.py`. SQLite locally, Postgres via `DATABASE_URL`. Alembic migrations now own schema changes; never rely on `create_all` for evolving customer schemas.
4. **Features are causal** (supplier stats only from deliveries completed before the order) and **prediction is
   stateless** from the frozen snapshot in the artifact (ADR 0001). Never query the DB from `ml.predict`.
5. **No double-booking** is an invariant of the scheduler; any new booking path re-checks overlap.
6. **Honest numbers.** Never show a sample or fallback number as real; a missing input is an error, not a default.
   Synthetic results always say "synthetic". `tests/test_pitch_claims.py` guards README/deck claims.
7. **Security:** mutating endpoints need `require_admin` (or scoped actor permissions after E2); machine ingest is HMAC
   signed (`api/signing.py`); secrets only via env (`.env.example` lists them); never commit `.env`, `*.db`,
   `ml/artifacts/*.joblib` from a customer.
8. **Customer data stays in Kazakhstan** (or on the customer's server). Render is for the synthetic demo only.
9. **The HTML console (`static/index.html`) is the product UI**; Streamlit is an internal analyst view. The receiving surface is `static/receiving.html`, linked from the legacy console and served as customer root; Russian UI text. Keep its offline shell separate from public demo APIs.

## Working rules for Claude Code
- Run `git status` before editing; another session may be working here.
- Match existing naming and structure; reuse the selected stack. Alembic/Caddy/Playwright were selected for the authorised receiving implementation; unrequested expansions still need a concrete use case.
- Every new pure function gets a known-answer test; every new endpoint gets an API test using the fixtures in
  `tests/conftest.py` (`api_client`, `seeded_client`, `temp_db`).
- Do not call a task done until its tests ran; report "untested" otherwise.
- One commit per finished stage, clear message. Push only when the user says so.
