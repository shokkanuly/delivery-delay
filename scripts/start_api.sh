#!/bin/sh
# Expand the platform port inside a shell, including Railway custom commands.
set -eu
cd "$(dirname "$0")/.."
exec python -m uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
