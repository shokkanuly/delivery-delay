"""Real browser → API → database rehearsal, including offline reload and interrupted photo sync.

Run with requirements-dev.txt and `python -m playwright install chromium` installed.
Uses only temporary synthetic data and prints no credentials.
"""
from __future__ import annotations

import argparse
import base64
from copy import deepcopy
from uuid import uuid4
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
from scripts.verify_receipt_bundle import verify as verify_bundle

ROOT = Path(__file__).resolve().parents[1]
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jB9kAAAAASUVORK5CYII=')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser',choices=['chromium','firefox','webkit'],default='chromium')
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
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
        if args.browser!='chromium':
            out=out/args.browser
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
                    launch_options={}
                    if args.browser=='firefox':
                        launch_options['firefox_user_prefs']={'permissions.default.geo':2}
                    if args.browser=='firefox' and sys.platform=='darwin':
                        # Keep test app-data separate from the user's Firefox state.
                        # https://github.com/microsoft/playwright/issues/42768
                        app_data=Path(tmp)/'firefox-app-data'
                        app_data.mkdir()
                        launch_options['env']={**os.environ,'CFFIXED_USER_HOME':str(app_data)}
                    browser = getattr(pw,args.browser).launch(**launch_options)
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
                    page.locator('[data-view="coverage"]').click()
                    page.locator('#coverage-form [name="start"]').fill('2026-11-02T00:00')
                    page.locator('#coverage-form [name="end"]').fill('2026-11-03T00:00')
                    page.locator('#coverage-form [name="eligible_arrivals"]').fill('2')
                    page.locator('#coverage-form [name="register_reference"]').fill('Synthetic independent register')
                    page.locator('#coverage-form button').click()
                    expect(page.locator('#coverage-result')).to_contain_text('Synthetic independent register')
                    with page.expect_download() as coverage_download:
                        page.locator('#download-coverage').click()
                    coverage_path=out/'coverage-report.json'
                    coverage_download.value.save_as(coverage_path)
                    report=json.loads(coverage_path.read_text())
                    assert report['site_id']==site['id'] and report['eligible_arrivals']==2 and report['recorded']==0
                    checks.append('Coordinator coverage report preserves the independent denominator and excludes SIM')
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
                    page.locator('#evidence-files').set_input_files({'name': 'synthetic.png', 'mimeType': 'application/octet-stream', 'buffer': PNG})
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
                    page.evaluate("() => {if(navigator.storage) navigator.storage.persist=()=>new Promise(()=>{});}")
                    page.locator('#capture-form button[type="submit"]').click()
                    expect(page.locator('#queue-list')).to_contain_text('SIM-1042')
                    assert page.evaluate("new Promise(resolve=>{const r=indexedDB.open('sitepulse-receiving-v1');r.onsuccess=()=>{const q=r.result.transaction('drafts').objectStore('drafts').getAll();q.onsuccess=()=>resolve(q.result[0].files[0].bytes instanceof ArrayBuffer);}})")
                    if args.browser=='chromium':
                        page.evaluate("new Promise((resolve,reject)=>{const r=indexedDB.open('sitepulse-receiving-v1');r.onsuccess=()=>{const tx=r.result.transaction('drafts','readwrite'),store=tx.objectStore('drafts'),q=store.getAll();q.onsuccess=()=>{const d=q.result[0];d.files=d.files.map(f=>({name:f.name,type:'application/octet-stream',blob:new Blob([f.bytes],{type:'application/octet-stream'})}));store.put(d);};tx.oncomplete=resolve;tx.onerror=reject;}})")
                        checks.append('Existing Blob-based v1 drafts remain compatible with byte-based new drafts')
                    page.reload()
                    expect(page.locator('#queue-list')).to_contain_text('SIM-1042')
                    assert page.locator('#credential').input_value() == ''
                    page.screenshot(path=str(out / 'offline-mobile.png'), full_page=True)
                    checks.append('Offline capture survives reload; a pending storage-persistence prompt cannot delay the saved-draft acknowledgement')
                    context.set_offline(False)
                    page.locator('#credential').fill(actor['credential'])
                    page.locator('#login-form button').click()
                    expect(page.locator('#login-panel')).to_be_hidden()
                    page.locator('[data-view="queue"]').click()
                    page.evaluate("() => {window.originalFetch=window.fetch;window.fetch=(...args)=>String(args[0]).endsWith('/attachments')?Promise.reject(new TypeError('Injected upload interruption')):window.originalFetch(...args);}")
                    page.locator('#sync-all').click()
                    expect(page.locator('#queue-list p.danger').first).to_be_visible()
                    assert client.get('/receiving/receipts', headers=auth).json()['total'] == 1
                    page.evaluate('() => {window.fetch=window.originalFetch;}')
                    page.locator('#sync-all').click()
                    expect(page.locator('#queue-list')).to_contain_text('Получено сервером')
                    records = client.get('/receiving/receipts', headers=auth).json()
                    assert records['total'] == 1 and len(records['receipts'][0]['current']['attachments']) == 1
                    media_id=records['receipts'][0]['current']['attachments'][0]['id']
                    assert client.get('/receiving/attachments/'+media_id,headers=auth).content==PNG
                    checks.append('Interrupted photo sync retries without duplicate receipts or attachments; downloaded bytes match')
                    page.locator('[data-open-draft]').click()
                    page.locator('[data-accepted-line]').fill('9')
                    page.locator('#decision-form button').click()
                    expect(page.locator('#receipt-detail .page-heading')).to_contain_text('Подтверждено')
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Receipt detail overflows phone viewport'
                    page.screenshot(path=str(out / 'confirmed-mobile.png'), full_page=True)
                    receipt_id = records['receipts'][0]['receipt_id']
                    packet = client.get(f'/receiving/receipts/{receipt_id}', headers=auth).json()
                    assert packet['current']['partial_acceptance'] and not packet['current']['complete_confirmed']
                    page.locator('[data-view="today"]').click()
                    page.locator(f'[data-open-plan="{plan["id"]}"]').click()
                    expect(page.locator('#plan-detail')).to_contain_text('Принято частично')
                    expect(page.locator('.quantity-grid dd').nth(2)).to_have_text('9')
                    expect(page.locator('.quantity-grid dd').nth(3)).to_have_text('1.25')
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    page.screenshot(path=str(out/'plan-progress-mobile.png'),full_page=True)
                    page.locator('#plan-detail details summary').click()
                    page.locator('#plan-status-form [name="reason"]').fill('Учебное закрытие после проверки')
                    page.locator('#plan-status-form button').click()
                    expect(page.locator('#plan-detail .page-heading')).to_contain_text('Завершено')
                    page.locator('[data-plan-receipt]').click()
                    page.locator('#correct-packet').click()
                    assert page.locator('#capture-plan').input_value()==plan['id'], 'Correction must retain its closed plan'
                    page.locator('#capture-lines [data-field="quantity"]').fill('8.5')
                    page.locator('#correction-reason').fill('Уточнено по весовому талону')
                    page.evaluate("() => {if(navigator.storage)navigator.storage.persist=async()=>{throw new Error('Synthetic persistence permission denied')};}")
                    page.locator('#evidence-files').set_input_files({'name': 'synthetic.png', 'mimeType': 'image/png', 'buffer': PNG})
                    page.locator('#capture-form button[type="submit"]').click()
                    try:
                        expect(page.locator('#view-queue')).to_be_visible()
                    except Exception:
                        page.screenshot(path=str(out/'correction-save-failure.png'),full_page=True)
                        diagnostic=page.evaluate("({message:document.getElementById('message').textContent,invalid:[...document.getElementById('capture-form').elements].filter(e=>e.validity&&!e.validity.valid).map(e=>({id:e.id,name:e.name,reason:e.validationMessage}))})")
                        raise RuntimeError('Correction save failed: '+json.dumps(diagnostic,ensure_ascii=False))
                    page.locator('#sync-all').click()
                    expect(page.locator('[data-open-draft]')).to_have_count(2)
                    packet = client.get(f'/receiving/receipts/{receipt_id}', headers=auth).json()
                    assert packet['current_revision'] == 2 and packet['current']['attestations'] == []
                    assert packet['current']['payload']['plan_id']==plan['id']
                    assert packet['revisions'][0]['attestations'][0]['accepted'][0]['quantity'] == '9'
                    checks.append('Plan totals show partial acceptance; correcting a closed plan retains its association and invalidates old acceptance')
                    page.locator('[data-open-draft]').first.click()
                    with page.expect_download() as evidence_download:
                        page.locator('#export-bundle').click()
                    evidence_path=out/'synthetic-receipt.zip'
                    evidence_download.value.save_as(evidence_path)
                    verified=verify_bundle(evidence_path)
                    assert verified['valid'] and verified['revisions']==2 and verified['attachments']==2
                    page.locator('[data-view="queue"]').click()
                    checks.append('One downloadable evidence ZIP includes and verifies both revisions and their exact files')

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
                    invalid=deepcopy(json.loads(contents));invalid['records'][1]['files'][0]['data']='broken'
                    page.locator('#import-drafts').set_input_files({'name':'invalid.json','mimeType':'application/json','buffer':json.dumps(invalid).encode()})
                    expect(page.locator('#message')).to_contain_text('Неподдерживаемый файл')
                    count_drafts="new Promise(resolve=>{const r=indexedDB.open('sitepulse-receiving-v1');r.onsuccess=()=>{const q=r.result.transaction('drafts').objectStore('drafts').count();q.onsuccess=()=>resolve(q.result);}})"
                    assert page.evaluate(count_drafts)==0
                    page.evaluate("() => {window.originalAdd=IDBObjectStore.prototype.add;window.restoreAdds=0;IDBObjectStore.prototype.add=function(...args){if(this.name==='drafts'&&++window.restoreAdds===2)throw new DOMException('Injected restore quota','QuotaExceededError');return window.originalAdd.apply(this,args);};}")
                    page.locator('#import-drafts').set_input_files(str(backup_path))
                    expect(page.locator('#message')).to_contain_text('Хранилище устройства заполнено')
                    assert page.evaluate(count_drafts)==0
                    page.evaluate('() => {IDBObjectStore.prototype.add=window.originalAdd;}')
                    page.locator('#import-drafts').set_input_files(str(backup_path))
                    expect(page.locator('#message')).to_contain_text('Восстановлено: 2')
                    expect(page.locator('#queue-list')).to_contain_text('SIM-1042')
                    page.locator('#import-drafts').set_input_files(str(backup_path))
                    expect(page.locator('#message')).to_contain_text('Совпадающих записей без изменений: 2')
                    conflict=deepcopy(json.loads(contents))
                    new_id=str(uuid4());conflict['records'][0]['id']=new_id;conflict['records'][0]['body']['operation_id']=new_id
                    conflict['records'][1]['body']['payload']['note']='Changed content under the same operation ID'
                    page.locator('#import-drafts').set_input_files({'name':'conflict.json','mimeType':'application/json','buffer':json.dumps(conflict).encode()})
                    expect(page.locator('#message')).to_contain_text('Конфликт:')
                    assert page.evaluate(count_drafts)==2
                    changed_file=deepcopy(json.loads(contents))
                    changed_file['records'][0]['files'][0]['data']='data:image/png;base64,'+base64.b64encode(PNG+b'changed').decode()
                    page.locator('#import-drafts').set_input_files({'name':'changed-file.json','mimeType':'application/json','buffer':json.dumps(changed_file).encode()})
                    expect(page.locator('#message')).to_contain_text('Конфликт:')
                    assert page.evaluate(count_drafts)==2
                    checks.append('Invalid, quota-failed and conflicting backup restores add nothing; identical imports preserve existing drafts')
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
                    other_site=client.post('/receiving/sites',json={'name':'Другой учебный объект'}).json()
                    other_actor=client.post(f"/receiving/sites/{other_site['id']}/actors",json={'name':'Другой координатор','role':'coordinator'}).json()
                    page.locator('#credential').fill(other_actor['credential'])
                    page.locator('#login-form button').click()
                    expect(page.locator('#site-name')).to_have_text('Другой учебный объект')
                    expect(page.locator('#plan-list')).to_contain_text('Нет ожидаемых поставок')
                    page.locator('[data-view="coverage"]').click()
                    expect(page.locator('#coverage-result')).to_be_empty()
                    page.locator('[data-view="queue"]').click()
                    expect(page.locator('#queue-list')).to_contain_text('Локальных записей нет')
                    page.locator('[data-view="capture"]').click()
                    expect(page.locator('#capture-plan option')).to_have_count(1)
                    assert page.locator('#capture-ref').input_value()==''
                    checks.append('Switching site/person clears prior reports, capture fields and visible drafts')

                    assert not errors, errors
                    browser.close()
                result = {'passed': True, 'browser':args.browser, 'checks': checks, 'data': 'synthetic browser rehearsal only'}
                (out / 'browser-report.json').write_text(json.dumps(result, indent=2))
                print(json.dumps(result, indent=2))
        finally:
            process.terminate()
            process.wait(timeout=15)
            log.close()


if __name__ == '__main__':
    main()
