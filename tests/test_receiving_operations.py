import json
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from db.migrate import upgrade
from scripts.receiving_backup import backup, restore


def test_backup_restore_includes_attachment_bytes(tmp_path):
    path = tmp_path / 'source.db'
    engine = create_engine(f'sqlite:///{path}')
    upgrade(engine)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE restore_canary (id INTEGER PRIMARY KEY, content BLOB)"))
        conn.execute(text("INSERT INTO restore_canary VALUES (1, :content)"), {'content': b'private-evidence-bytes'})
    saved = tmp_path / 'backup.db'
    manifest = backup(str(engine.url), saved)
    assert manifest['bytes'] > 0 and saved.stat().st_mode & 0o777 == 0o600
    target = tmp_path / 'restored.db'
    assert restore(f'sqlite:///{target}', saved)['includes_attachments']
    restored = create_engine(f'sqlite:///{target}')
    with restored.connect() as conn:
        assert conn.execute(text('SELECT content FROM restore_canary')).scalar() == b'private-evidence-bytes'
    with pytest.raises(ValueError, match='new SQLite'):
        restore(f'sqlite:///{target}', saved)
    saved.write_bytes(saved.read_bytes() + b'tampered')
    with pytest.raises(ValueError, match='digest'):
        restore(f'sqlite:///{tmp_path / "other.db"}', saved)


def test_customer_profile_does_not_seed_or_serve_public_legacy_data(temp_db, monkeypatch):
    monkeypatch.setenv('SITEPULSE_MODE', 'customer')
    from fastapi.testclient import TestClient
    from api.main import app
    with TestClient(app) as client:
        assert client.get('/readyz').status_code == 200
        assert client.get('/receive').status_code == 200
        assert client.get('/').status_code == 200
        for path in ['/projects', '/health', '/metrics', '/static/samples/audit_report_synthetic.json', '/static/index.html', '/docs']:
            assert client.get(path).status_code == 404
        assert client.get('/receiving/me').status_code == 401
        assert client.get('/receiving/me').headers['cache-control'] == 'no-store'
        assert client.post('/receiving/receipts', content=b'x' * (256 * 1024 + 1)).status_code == 413
    with temp_db['Session']() as db:
        assert db.query(temp_db['models'].Project).count() == 0
        assert db.query(temp_db['models'].PredictionLog).count() == 0
    with pytest.raises(RuntimeError, match='disabled'):
        temp_db['seed'].seed()


@pytest.mark.skipif(not os.getenv('SITEPULSE_TEST_POSTGRES_URL'), reason='Set an isolated PostgreSQL rehearsal URL')
def test_postgres_legacy_upgrade_and_metadata_match():
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from db.database import Base
    import db.models
    from migrations.legacy_schema import Base as LegacyBase
    engine = create_engine(os.environ['SITEPULSE_TEST_POSTGRES_URL'])
    # Never drop anything: this test requires an explicitly empty rehearsal database.
    assert not inspect(engine).get_table_names(), 'Use an empty, disposable PostgreSQL database'
    LegacyBase.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO suppliers(id, name) VALUES ('preserve-me', 'Synthetic migration canary')"))
    upgrade(engine)
    upgrade(engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT name FROM suppliers WHERE id='preserve-me'")).scalar() == 'Synthetic migration canary'
        differences = compare_metadata(MigrationContext.configure(conn), Base.metadata)
        assert differences == []
    engine.dispose()


def test_backup_restores_real_receipt_tables_and_media(api_client, temp_db, tmp_path):
    from uuid import uuid4
    from sqlalchemy.orm import Session
    client = api_client
    site = client.post('/receiving/sites', json={'name':'Synthetic recovery rehearsal'}).json()
    actor = client.post(f"/receiving/sites/{site['id']}/actors", json={'name':'Synthetic receiver','role':'receiver'}).json()
    auth = {'Authorization':'Bearer '+actor['credential']}
    receipt_id = str(uuid4())
    response = client.post('/receiving/receipts', headers=auth, json={
        'receipt_id':receipt_id, 'operation_id':str(uuid4()), 'payload':{
            'reference':'SIM-RESTORE', 'observed_at':'2026-11-02T10:00:00+05:00',
            'time_source':'device', 'provenance':'SIM', 'condition':'ok',
            'lines':[{'line_id':'1','material':'Synthetic rebar','quantity':'2','unit':'t'}]}})
    assert response.status_code == 201, response.text
    content = b'\x89PNG\r\n\x1a\nsynthetic-restore-photo'
    media = client.post(f'/receiving/receipts/{receipt_id}/revisions/1/attachments', headers=auth,
                        files={'file':('synthetic.png',content,'image/png')})
    assert media.status_code == 201
    postgres = temp_db['engine'].dialect.name == 'postgresql'
    if postgres:
        target_url = os.getenv('SITEPULSE_TEST_RESTORE_URL')
        if not target_url:
            pytest.skip('Set an empty PostgreSQL restore target and install pg_dump/pg_restore')
        # This fixture's schema is unique; pg_dump includes it alongside public tables.
        schema = temp_db['engine'].url.query.get('options')
        with temp_db['engine'].connect() as conn:
            schema = conn.execute(text('SELECT current_schema()')).scalar()
    else:
        target_url = f'sqlite:///{tmp_path / "restored-evidence.db"}'
    saved = tmp_path / ('evidence.dump' if postgres else 'evidence.db')
    backup(temp_db['engine'].url.render_as_string(hide_password=False), saved)
    restore(target_url, saved)
    restored = create_engine(target_url, **({'connect_args':{'options':f'-csearch_path={schema}'}} if postgres else {}))
    with Session(restored) as db:
        row = db.get(temp_db['models'].Receipt, receipt_id)
        attachment = db.get(temp_db['models'].ReceiptAttachment, media.json()['id'])
        assert row.revision == 1
        assert attachment.content == content and attachment.site_id == site['id']
        assert db.query(temp_db['models'].ReceiptRevision).filter_by(receipt_id=receipt_id).one().payload['reference'] == 'SIM-RESTORE'
    restored.dispose()
