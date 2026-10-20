# Contributing to SitePulse

Use Python 3.11 or 3.12. Create/activate `.venv`, install `requirements.txt`, then run `./start.sh`.
The product is at port 8000; Streamlit at 8501 is the internal analyst view.

## Checks before a PR

```bash
python -m pytest
python -m scripts.build_demo_report --check
python run.py
```

If Docker is installed, copy `.env.example` to `.env`, set a private key and run
`docker compose config -q` and `docker build -t sitepulse:check .`.
Never commit `.env`, databases, uploaded customer files or model artifacts.

## Invariants

- `ml/`, `engines/` and `business/` import no web frameworks; calls go down through the layers.
- Supplier features use completed history strictly before the order. Online scoring uses the
  artifact's frozen snapshot, not database queries.
- Every scheduling path checks equipment overlap. Solver output is a proposal, not human approval.
- Keep one router per domain; typed API contracts live in `api/schemas.py`.
- All sample data and results are labelled synthetic. Missing evidence stays missing.
- Do not invent interviews, partners, customers, market size or measured savings in a demo.

Change shared audit rules in `ml/audit.py`, then regenerate the public sample with
`python -m scripts.build_demo_report`. The public JSON must describe the exact downloadable CSV.
Existing private-upload authentication must remain intact. Add meaningful known-answer or
integration coverage for new logic; documentation-only changes do not need mirrored tests.

Read [CLAUDE.md](CLAUDE.md), the [architecture](docs/ARCHITECTURE.md) and
[current plan](docs/plans/mvp-reshape.md). New dependencies require founder approval.
