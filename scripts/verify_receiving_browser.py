"""Real browser → API → database rehearsal, including offline reload and interrupted photo sync.

Run with requirements-dev.txt and `python -m playwright install chromium` installed.
Uses only temporary synthetic data and prints no credentials.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time

import httpx
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jB9kAAAAASUVORK5CYII=')


def main():
    with tempfile.TemporaryDirectory() as tmp:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        key = secrets.token_urlsafe(32)
        env = dict(os.environ, DATABASE_URL=f'sqlite:///{tmp}/browser.db', SITEPULSE_MODE='customer',
                   SITEPULSE_ADMIN_KEY=key, OMP_NUM_THREADS='1',
                   SITEPULSE_ENABLE_OPERATIONS='1', SITEPULSE_ENABLE_RECONCILIATION='1')
        log = open(Path(tmp) / 'server.log', 'w')
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'api.main:app', '--host', '127.0.0.1', '--port', str(port)], cwd=ROOT, env=env, stdout=log, stderr=log)
        out = ROOT / 'test-results' / 'receiving'
        out.mkdir(parents=True, exist_ok=True)
        checks = []
        try:
            with httpx.Client(base_url=base, headers={'X-API-Key': key}) as client:
                for _ in range(100):
                    try:
                        if client.get('/readyz').status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(.2)
                else:
                    raise RuntimeError('Rehearsal server did not start')
                site = client.post('/receiving/sites', json={'name': 'Учебный объект · проверка'}).json()
                actor = client.post(f"/receiving/sites/{site['id']}/actors", json={'name': 'Учебный координатор', 'role': 'coordinator'}).json()
                auth = {'Authorization': 'Bearer ' + actor['credential']}
                plan = client.post('/receiving/plans', headers=auth, json={'reference': 'SIM-1042', 'supplier': 'Учебный поставщик', 'promised_date': '2026-11-02', 'provenance': 'SIM', 'lines': [{'line_id': '1', 'material': 'Арматура', 'quantity': '10.25', 'unit': 'т'}]}).json()
                with sync_playwright() as pw:
                    browser = pw.chromium.launch()
                    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                    page = context.new_page()
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(base + '/receive')
                    page.locator('#credential').fill(actor['credential'])
                    page.locator('#login-form button').click()
                    expect(page.locator('#plan-list')).to_contain_text('SIM-1042')
                    page.screenshot(path=str(out / 'today-desktop.png'), full_page=True)
                    checks.append('Named login and plan list render from API data')
                    page.locator('[data-view="slots"]').click()
                    page.locator('#resource-editor summary').click()
                    page.locator('#resource-form [name="name"]').fill('Учебный кран К-01')
                    page.locator('#resource-form button').click()
                    expect(page.locator('#slot-resource option')).to_have_count(1)
                    page.locator('#slot-editor summary').click()
                    page.locator('#slot-form [name="start_at"]').fill('2026-11-02T10:00')
                    page.locator('#slot-form [name="end_at"]').fill('2026-11-02T11:00')
                    page.locator('#slot-form button').click()
                    expect(page.locator('#slot-list')).to_contain_text('Запрошено')
                    page.once('dialog', lambda dialog: dialog.accept('Учебное одобрение'))
                    page.locator('[data-action="approve"]').click()
                    expect(page.locator('#slot-list')).to_contain_text('Одобрено')
                    page.screenshot(path=str(out / 'slots-desktop.png'), full_page=True)
                    page.locator('[data-view="documents"]').click()
                    page.locator('#view-documents summary').click()
                    page.locator('#document-form [name="number"]').fill('SIM-DOC-1')
                    page.locator('#document-form [name="issuer"]').fill('Учебный поставщик')
                    page.locator('#document-form [name="issued_on"]').fill('2026-11-02')
                    page.locator('#document-lines [data-field="material"]').fill('Арматура')
                    page.locator('#document-lines [data-field="quantity"]').fill('10.25')
                    page.locator('#document-lines [data-field="unit"]').fill('т')
                    page.locator('#document-form button[type="submit"]').click()
                    expect(page.locator('#document-list')).to_contain_text('SIM-DOC-1')
                    checks.append('Optional resource request/approval and manual document entry work in the browser')

                    page.evaluate('navigator.serviceWorker.ready')
                    page.wait_for_function('navigator.serviceWorker.controller !== null')
                    page.set_viewport_size({'width': 390, 'height': 844})
                    page.locator('[data-view="capture"]').click()
                    page.locator('#capture-plan').select_option(plan['id'])
                    page.locator('#evidence-files').set_input_files({'name': 'synthetic.png', 'mimeType': 'image/png', 'buffer': PNG})
                    page.locator('#get-location').click()
                    expect(page.locator('#location-status')).to_contain_text('Нет разрешения', timeout=15000)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Capture form overflows phone viewport'
                    page.screenshot(path=str(out / 'capture-mobile.png'), full_page=True)
                    context.set_offline(True)
                    page.evaluate("() => {window.originalPut=IDBObjectStore.prototype.put; IDBObjectStore.prototype.put=function(){throw new DOMException('Synthetic quota failure','QuotaExceededError')};}")
                    page.locator('#capture-form button[type="submit"]').click()
                    expect(page.locator('#message')).to_contain_text('Запись НЕ сохранена')
                    assert page.locator('#capture-ref').input_value() == 'SIM-1042'
                    assert page.locator('#evidence-files').evaluate('(el)=>el.files.length') == 1
                    page.evaluate('() => {IDBObjectStore.prototype.put=window.originalPut;}')
                    checks.append('Storage quota failure leaves the entered receipt and photo intact for recovery')
                    page.locator('#capture-form button[type="submit"]').click()
                    expect(page.locator('#queue-list')).to_contain_text('SIM-1042')
                    page.reload()
                    expect(page.locator('#queue-list')).to_contain_text('SIM-1042')
                    assert page.locator('#credential').input_value() == ''
                    page.screenshot(path=str(out / 'offline-mobile.png'), full_page=True)
                    checks.append('Offline capture with photo survives a full page reload; denied GPS remains explicit')
                    context.set_offline(False)
                    page.locator('#credential').fill(actor['credential'])
                    page.locator('#login-form button').click()
                    expect(page.locator('#login-panel')).to_be_hidden()
                    page.locator('[data-view="queue"]').click()
                    context.route('**/receiving/receipts/*/revisions/*/attachments', lambda route: route.abort())
                    page.locator('#sync-all').click()
                    expect(page.locator('#queue-list p.danger').first).to_be_visible()
                    assert client.get('/receiving/receipts', headers=auth).json()['total'] == 1
                    context.unroute('**/receiving/receipts/*/revisions/*/attachments')
                    page.locator('#sync-all').click()
                    expect(page.locator('#queue-list')).to_contain_text('Получено сервером')
                    records = client.get('/receiving/receipts', headers=auth).json()
                    assert records['total'] == 1 and len(records['receipts'][0]['current']['attachments']) == 1
                    checks.append('Interrupted photo sync retries without duplicate receipts or attachments')
                    page.locator('[data-open-draft]').click()
                    page.locator('[data-accepted-line]').fill('9')
                    page.locator('#decision-form button').click()
                    expect(page.locator('#receipt-detail .page-heading')).to_contain_text('Подтверждено')
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Receipt detail overflows phone viewport'
                    page.screenshot(path=str(out / 'confirmed-mobile.png'), full_page=True)
                    receipt_id = records['receipts'][0]['receipt_id']
                    packet = client.get(f'/receiving/receipts/{receipt_id}', headers=auth).json()
                    assert packet['current']['partial_acceptance'] and not packet['current']['complete_confirmed']
                    page.locator('#correct-packet').click()
                    page.locator('#capture-lines [data-field="quantity"]').fill('8.5')
                    page.locator('#correction-reason').fill('Уточнено по весовому талону')
                    page.locator('#evidence-files').set_input_files({'name': 'synthetic.png', 'mimeType': 'image/png', 'buffer': PNG})
                    page.locator('#capture-form button[type="submit"]').click()
                    page.locator('#sync-all').click()
                    expect(page.locator('[data-open-draft]')).to_have_count(2)
                    packet = client.get(f'/receiving/receipts/{receipt_id}', headers=auth).json()
                    assert packet['current_revision'] == 2 and packet['current']['attestations'] == []
                    assert packet['revisions'][0]['attestations'][0]['accepted'][0]['quantity'] == '9'
                    checks.append('Partial acceptance is explicit; correction preserves old decision and requires a new confirmation')
                    with page.expect_download() as download:
                        page.locator('#export-drafts').click()
                    downloaded = download.value
                    backup_path = out / 'synthetic-drafts.json'
                    downloaded.save_as(backup_path)
                    contents = backup_path.read_text()
                    assert actor['credential'] not in contents and len(json.loads(contents)['records']) == 2
                    cached = page.evaluate('caches.keys().then(async keys => (await Promise.all(keys.map(async k => (await (await caches.open(k)).keys()).map(r=>r.url)))).flat())')
                    assert not any('/receiving/' in url for url in cached)
                    assert page.evaluate('Object.keys(localStorage).length') == 0
                    checks.append('Draft backup contains media but no credentials; service worker caches no private API responses')
                    page.evaluate("new Promise((resolve,reject)=>{const r=indexedDB.open('sitepulse-receiving-v1');r.onsuccess=()=>{const tx=r.result.transaction('drafts','readwrite');tx.objectStore('drafts').clear();tx.oncomplete=resolve;tx.onerror=reject;}})")
                    page.locator('#import-drafts').set_input_files(str(backup_path))
                    expect(page.locator('#queue-list')).to_contain_text('SIM-1042')
                    page.locator('#sync-all').click()
                    expect(page.locator('[data-open-draft]')).to_have_count(2)
                    assert client.get('/receiving/receipts', headers=auth).json()['total'] == 1
                    checks.append('Exported draft backup restores media and resends the original IDs without duplication')

                    page.locator('[data-view="capture"]').click()
                    page.locator('#capture-ref').fill('SIM-REVOKED')
                    page.locator('#capture-lines [data-field="material"]').fill('Цемент')
                    page.locator('#capture-lines [data-field="quantity"]').fill('1')
                    page.locator('#capture-lines [data-field="unit"]').fill('т')
                    page.locator('#capture-form button[type="submit"]').click()
                    client.post(f"/receiving/actors/{actor['id']}/revoke")
                    page.locator('#sync-all').click()
                    expect(page.locator('#login-panel')).to_be_visible()
                    expect(page.locator('#queue-list')).to_contain_text('SIM-REVOKED')
                    assert client.get('/receiving/receipts', headers=auth).status_code == 401
                    checks.append('Revoked access blocks sync and leaves unsent evidence recoverable')
                    assert not errors, errors
                    browser.close()
                result = {'passed': True, 'checks': checks, 'data': 'synthetic browser rehearsal only'}
                (out / 'browser-report.json').write_text(json.dumps(result, indent=2))
                print(json.dumps(result, indent=2))
        finally:
            process.terminate()
            process.wait(timeout=15)
            log.close()


if __name__ == '__main__':
    main()
