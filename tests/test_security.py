"""Admin endpoints need X-API-Key; without a configured key they are closed."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_admin_endpoints_reject_missing_or_wrong_key(temp_db, monkeypatch):
    import api.main as main
    monkeypatch.setenv("SITEPULSE_ADMIN_KEY", "right")
    c = TestClient(main.app)
    assert c.post("/train").status_code == 401
    assert c.post("/outcomes", json=[], headers={"X-API-Key": "wrong"}).status_code == 401


def test_admin_endpoints_closed_when_unconfigured(temp_db, monkeypatch):
    import api.main as main
    monkeypatch.delenv("SITEPULSE_ADMIN_KEY", raising=False)
    assert TestClient(main.app).post("/train").status_code == 503


def test_cors_is_not_wildcard_with_credentials():
    from api.security import cors_origins
    assert "*" not in cors_origins()
