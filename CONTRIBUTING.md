# Contributing to Construction Logistics Platform (SitePulse)

Thank you for contributing to the SitePulse Construction Logistics Platform (designed for regional construction holdings). This guide outlines our engineering workflows, testing requirements, and code standards.

---

## 1. Development Setup

### Prerequisites
* Python 3.11 or 3.12
* Docker & Docker Compose (optional for local full-stack run)
* Virtual environment (`venv`)

### Installation
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pytest
```

### Running Locally
```bash
./start.sh
```
* Interactive Web Console: `http://localhost:8000/`
* API & Interactive Docs: `http://localhost:8000/docs`
* Streamlit Analytics: `http://localhost:8501/`

---

## 2. Architecture Invariants & Critical Rules

Every contributor must preserve the following architectural boundaries (see [ARCHITECTURE.md](docs/ARCHITECTURE.md) and [PRD.md](docs/PRD.md)):

1. **Strictly Causal Feature Engineering:**
   - Features used for delay prediction must never leak future information.
   - Any historical supplier statistics must only aggregate records with `completed_at < order_date`.
   - Running `pytest tests/test_features_leakage.py` validates that the causal-vs-leaky guard passes.
2. **Stateless Online Prediction:**
   - Online scoring (`ml.predict:score`) reads from the frozen `feature_snapshot` in the trained artifact (`ml/artifacts/model.joblib`), never from a live database query.
3. **Cold-Start Resilience:**
   - Brand new suppliers or routes must never produce `NaN` or 500 errors. They must shrink smoothly onto material × route priors via Empirical Bayes shrinkage.
4. **Guaranteed 0 Double-Bookings:**
   - The OR-Tools scheduler in `engines/scheduler/solver.py` must maintain the `AddNoOverlap` invariant for physical machinery.

---

## 3. Testing & Validation Checklist

Before submitting a Pull Request, verify that all test suites pass:

```bash
# 1. Run all unit and integration tests
pytest

# 2. Run the end-to-end ML correctness demo
python3 run.py

# 3. Validate Docker Compose configuration
cp .env.example .env
docker compose config -q
```

---

## 4. Pull Request Checklist

- [ ] All 70+ tests in `tests/` pass with 0 errors.
- [ ] No future leakage introduced into `ml/features.py`.
- [ ] Code follows PEP 8 styling with type hints on public functions.
- [ ] Updated documentation or ADRs in `docs/adr/` if modifying core data flows or solver constraints.
- [ ] Added or updated test coverage for new endpoints or logic.
