# CLAUDE.md — SitePulse (repo: shokkanuly/delivery-delay)

SitePulse gives a construction contractor a closed delivery-risk loop for one site: 1C export in → supplier scorecard
and at-risk list out → crane/gate slots without double-booking → actual arrivals back in → accuracy measured.
No customers yet; all bundled data is synthetic and must be labelled so.

**Current work:** `docs/plans/mvp-reshape.md`. Do one stage per session, in order. Read the whole plan first, mark the
stage `[~]`, build it, run its *Done when*, mark it `[x]`, and add a dated note to §7 of the plan.

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
3. **One schema of record:** `db/models.py`. SQLite locally, Postgres via `DATABASE_URL`. After Stage 5 every schema
   change needs an Alembic migration.
4. **Features are causal** (supplier stats only from deliveries completed before the order) and **prediction is
   stateless** from the frozen snapshot in the artifact (ADR 0001). Never query the DB from `ml.predict`.
5. **No double-booking** is an invariant of the scheduler; any new booking path re-checks overlap.
6. **Honest numbers.** Never show a sample or fallback number as real; a missing input is an error, not a default.
   Synthetic results always say "synthetic". `tests/test_pitch_claims.py` guards README/deck claims.
7. **Security:** mutating endpoints need `require_admin` (or `require_role` after Stage 6); machine ingest is HMAC
   signed (`api/signing.py`); secrets only via env (`.env.example` lists them); never commit `.env`, `*.db`,
   `ml/artifacts/*.joblib` from a customer.
8. **Customer data stays in Kazakhstan** (or on the customer's server). Render is for the synthetic demo only.
9. **The HTML console (`static/index.html`) is the product UI**; Streamlit is an internal analyst view. Add product
   views to the console following its existing view pattern; Russian UI text.

## Working rules for Claude Code
- Run `git status` before editing; another session may be working here.
- Match existing naming and structure; no new library, framework or pattern without asking (the plan marks the ones
  that need a yes: Alembic, openpyxl, Caddy).
- Every new pure function gets a known-answer test; every new endpoint gets an API test using the fixtures in
  `tests/conftest.py` (`api_client`, `seeded_client`, `temp_db`).
- Do not call a task done until its tests ran; report "untested" otherwise.
- One commit per finished stage, clear message. Push only when the user says so.
