#!/usr/bin/env bash
# One-command local run: ensures a trained model, starts the API, then the
# dashboard. Works from any directory. Ctrl-C stops both.
set -euo pipefail
cd "$(dirname "$0")"

PY=python3
API_HOST=127.0.0.1
API_PORT=8000
DASH_PORT=8501

# 1. Ensure a model artifact exists (seed the DB + train if not).
if [ ! -f ml/artifacts/model.joblib ]; then
  echo "No model artifact found — preparing data and training..."
  [ -f delivery.db ] || "$PY" -m db.seed
  "$PY" -m ml.train
fi

# 2. Start the API in the background; stop it when this script exits.
echo "Starting API      -> http://${API_HOST}:${API_PORT}  (docs at /docs)"
"$PY" -m uvicorn api.main:app --host "$API_HOST" --port "$API_PORT" --log-level warning &
API_PID=$!
trap 'echo; echo "Stopping..."; kill $API_PID 2>/dev/null || true' EXIT INT TERM

# 3. Wait for the API to become healthy.
for _ in $(seq 1 30); do
  curl -sf "http://${API_HOST}:${API_PORT}/health" >/dev/null 2>&1 && break
  sleep 1
done

# 4. Run the dashboard in the foreground (Ctrl-C here stops everything).
echo "Starting dashboard -> http://${API_HOST}:${DASH_PORT}"
API_URL="http://${API_HOST}:${API_PORT}" "$PY" -m streamlit run dashboard/app.py \
  --server.port "$DASH_PORT" --server.address "$API_HOST" --server.headless true
