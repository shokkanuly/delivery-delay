"""Access control.

Admin operations (retraining the model, recording ground-truth outcomes) need
the `X-API-Key` header to match the SITEPULSE_ADMIN_KEY environment variable.
The key lives server-side only: the Streamlit server sends it, the browser
console never sees it. With no key configured, admin endpoints are closed
(503) rather than open.

Workspaces use their own bearer secret: the server-issued access key.
"""
from __future__ import annotations

import os
import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

ADMIN_KEY_ENV = "SITEPULSE_ADMIN_KEY"
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_admin(key: str | None = Security(_api_key_header)) -> None:
    expected = os.getenv(ADMIN_KEY_ENV)
    if not expected:
        raise HTTPException(503, f"Admin endpoints are disabled: set {ADMIN_KEY_ENV}.")
    if not key or not secrets.compare_digest(key, expected):
        raise HTTPException(401, "Missing or invalid X-API-Key.")


def new_workspace_key() -> str:
    """128-bit URL-safe token: not guessable, unlike the old DEMO-PRJ-XXXXXX."""
    return "WS-" + secrets.token_urlsafe(16)


def cors_origins() -> list[str]:
    """Explicit origins only. The console is served by the API itself
    (same origin); only the Streamlit dashboard needs CORS."""
    raw = os.getenv("SITEPULSE_CORS_ORIGINS", "http://localhost:8501,http://127.0.0.1:8501")
    return [o.strip() for o in raw.split(",") if o.strip()]
