"""Receiving-only deployment and hosting limits, using disposable records."""
import io
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from api.receiving_app import create_receiving_app
from api.routers.receiving import evidence_limits
from scripts.verify_receipt_bundle import verify


def test_receiving_only_app_has_no_demo_routes_or_seed(temp_db, monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.delenv('SITEPULSE_MODE', raising=False)
    monkeypatch.setenv('SITEPULSE_ADMIN_KEY', 'test-operator-key')
    with TestClient(create_receiving_app()) as client:
        assert client.get('/readyz').json()['mode'] == 'customer'
        for path in ['/', '/receive']:
            response = client.get(path)
            assert response.status_code == 200
            assert 'frame-ancestors' in response.headers['content-security-policy']
        assert client.get('/receive-sw.js').headers['service-worker-allowed'] == '/'
        assert client.get('/static/receiving.js').status_code == 200
        for path in ['/docs', '/openapi.json', '/projects', '/predict', '/static/index.html',
                     '/static/samples/audit_report_synthetic.json']:
            assert client.get(path).status_code == 404
        assert client.get('/receiving/me').status_code == 401
        assert client.post('/receiving/sites', json={'name': 'Denied'}).status_code == 401
        site = client.post('/receiving/sites', headers={'X-API-Key': 'test-operator-key'},
                           json={'name': 'SIM hosted rehearsal'})
        assert site.status_code == 201
    with temp_db['Session']() as session:
        assert session.query(temp_db['models'].Project).count() == 0
        assert session.query(temp_db['models'].PredictionLog).count() == 0


def test_vercel_refuses_ephemeral_sqlite(temp_db, monkeypatch):
    monkeypatch.setenv('VERCEL', '1')
    # PostgreSQL fixtures exercise the other branch, not this SQLite guard.
    monkeypatch.setattr(temp_db['database'], 'engine',
                        SimpleNamespace(url=SimpleNamespace(get_backend_name=lambda: 'sqlite')))
    with pytest.raises(RuntimeError, match='persistent PostgreSQL'):
        with TestClient(create_receiving_app()):
            pass


def test_vercel_requires_private_operator_key_before_migration(temp_db, monkeypatch):
    monkeypatch.setenv('VERCEL', '1')
    monkeypatch.delenv('SITEPULSE_ADMIN_KEY', raising=False)
    monkeypatch.setattr(temp_db['database'], 'engine',
                        SimpleNamespace(url=SimpleNamespace(get_backend_name=lambda: 'postgresql')))
    with pytest.raises(RuntimeError, match='private SITEPULSE_ADMIN_KEY'):
        with TestClient(create_receiving_app()):
            pass


def test_host_limits_are_explicit_and_smaller_on_vercel(monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    assert evidence_limits() == {'media_bytes': 5 * 1024**2, 'bundle_bytes': 100 * 1024**2}
    monkeypatch.setenv('VERCEL', '1')
    assert evidence_limits() == {'media_bytes': 4 * 1024**2, 'bundle_bytes': 4 * 1024**2}


def test_vercel_limits_uploads_downloads_and_actual_zip_bytes(api_client, monkeypatch):
    client = api_client
    monkeypatch.setenv('VERCEL', '1')
    site = client.post('/receiving/sites', json={'name': 'SIM hosted'}).json()
    actor = client.post(f"/receiving/sites/{site['id']}/actors",
                        json={'name': 'SIM receiver', 'role': 'receiver'}).json()
    auth = {'Authorization': 'Bearer ' + actor['credential']}
    assert client.get('/receiving/me', headers=auth).json()['limits']['media_bytes'] == 4 * 1024**2
    receipt_id = str(uuid4())
    response = client.post('/receiving/receipts', headers=auth, json={
        'receipt_id': receipt_id, 'operation_id': str(uuid4()), 'payload': {
            'reference': 'SIM-LIMIT', 'observed_at': '2026-11-03T10:00:00+05:00',
            'time_source': 'manual', 'provenance': 'SIM', 'condition': 'ok',
            'lines': [{'line_id': '1', 'material': 'SIM rebar', 'quantity': '1', 'unit': 't'}]}})
    assert response.status_code == 201
    url = f'/receiving/receipts/{receipt_id}/revisions/1/attachments'
    png = b'\x89PNG\r\n\x1a\n'
    too_big = png + b'x' * (4 * 1024**2)
    assert client.post(url, headers=auth, files={'file': ('big.png', too_big, 'image/png')}).status_code == 413
    small = client.post(url, headers=auth, files={'file': ('small.png', png, 'image/png')}).json()
    assert client.get(f"/receiving/attachments/{small['id']}", headers=auth).content == png
    bundle_url = f'/receiving/receipts/{receipt_id}/bundle'
    bundle = client.get(bundle_url, headers=auth)
    assert verify(io.BytesIO(bundle.content))['attachments'] == 1
    # Include manifest/ZIP overhead, not only the raw evidence bytes.
    monkeypatch.setattr('api.routers.receiving.MAX_BUNDLE_BYTES', len(bundle.content) - 1)
    assert client.get(bundle_url, headers=auth).status_code == 413
    monkeypatch.setattr('api.routers.receiving.MAX_BUNDLE_BYTES', 100 * 1024**2)
    monkeypatch.delenv('VERCEL')
    old = client.post(url, headers=auth, files={'file': ('old.png', too_big, 'image/png')})
    assert old.status_code == 201
    monkeypatch.setenv('VERCEL', '1')
    assert client.get(f"/receiving/attachments/{old.json()['id']}", headers=auth).status_code == 413
    assert client.get(bundle_url, headers=auth).status_code == 413
