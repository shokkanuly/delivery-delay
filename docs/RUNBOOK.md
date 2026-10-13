# Operations & SRE Runbook
## Construction Logistics Platform (SitePulse)

This runbook outlines operational procedures, health monitoring, deployment commands, and incident response runbooks for operating the SitePulse Construction Logistics Platform.

---

## 1. Quickstart & Service Management

### Local Development
```bash
# 1. Complete stack launch (FastAPI on :8000 + Streamlit on :8501)
./start.sh

# 2. Or start individual services:
# API server with hot-reload:
python3 -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

# Streamlit Analytics Dashboard:
python3 -m streamlit run dashboard/app.py --server.port 8501 --server.address 127.0.0.1
```

### Docker Compose (Full Stack with PostgreSQL)
```bash
# Setup environment and launch containers
cp .env.example .env
docker compose up --build -d

# Check service health status
docker compose ps

# Follow centralized application logs
docker compose logs -f api
```

---

## 2. Health Monitoring & Endpoints

| Endpoint | Method | Expected Response | Description |
| :--- | :--- | :--- | :--- |
| `/health` | GET | `{"status": "ok", "engines": [...]}` | Heartbeat, active engines, trained row count. |
| `/metrics` | GET | Cross-validated scores, PR-AUC, lift | Model accuracy vs. baseline scorecard. |
| `/accuracy` | GET | `{"accuracy": 0.xx, "outcomes": n}` | Closed-loop verification of predictions vs. reality. |

### Health Check Alerting Rule
If `GET /health` returns non-200 or `x-process-time-ms > 500`:
1. Check process memory via `ps aux | grep uvicorn` or `docker stats`.
2. Inspect logs for uncaught exceptions in feature inference or OR-Tools solver.
3. If PostgreSQL is unresponsive, verify container connection string in `.env`.

---

## 3. Retraining & Model Management

The prediction engine is stateless and caches the model artifact in memory. When new delivery actuals arrive:

### Retrain Trigger
```bash
# Trigger hot-swapped retraining via API
curl -X POST http://127.0.0.1:8000/train

# Response:
# {"status": "retrained", "trained_rows": 2200, "metrics": {...}}
```
*Note: The API immediately clears its LRU cache and serves the new artifact with zero downtime.*

### CLI Manual Retraining
```bash
python3 -m ml.train data/synthetic/delay_prediction.csv
```

---

## 4. Incident Response & Troubleshooting

### Scenario A: Port Conflict (`Address already in use: 8000` or `8501`)
```bash
# Identify conflicting process
lsof -i :8000 -i :8501

# Terminate orphan process if necessary
kill -9 <PID>
```

### Scenario B: Cold-Start Supplier Warnings
* **Symptoms:** Supplier has no historical track record on a route.
* **Expected Behavior:** System automatically applies Bayesian shrinkage to material × route empirical priors.
* **Action:** No incident action required. Confirm `supplier_n_prior == 0` and `risk_band` reflects material priors rather than `NaN`.

### Scenario C: OR-Tools Solver Timeout
* **Symptoms:** `/schedule` latency exceeds 5 seconds.
* **Resolution:** Default time limit is 5.0 seconds. Check `booking_requests` dataset for cycle deadlocks or invalid time ranges ($T_{\text{end}} \le T_{\text{start}}$).
