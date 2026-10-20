#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
exec python -m streamlit run dashboard/app.py \
  --server.port "${PORT:-8501}" --server.address 0.0.0.0 --server.headless true
