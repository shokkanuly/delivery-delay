from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from engines.receiving import digest, reconciliation, receipt_summary

PNG = b"\x89PNG\r\n\x1a\n" + b"synthetic-test-evidence"


@pytest.fixture
def receiving(api_client, monkeypatch):
    monkeypatch.setenv("SITEPULSE_ENABLE_RECONCILIATION", "1")
    monkeypatch.setenv("SITEPULSE_ENABLE_PARTNER_SHARING", "1")
    client = api_client
    site = client.post('/receiving/sites', json={'name': 'Private site'}).json()
    actors = {}
    for role in ['coordinator', 'receiver', 'viewer']:
        response = client.post(f"/receiving/sites/{site['id']}/actors", json={'name': role, 'role': role})
        assert response.status_code == 201, response.text
        actors[role] = response.json()
    auth = lambda role='coordinator': {'Authorization': 'Bearer ' + actors[role]['credential']}
    plan_body = {'reference': 'TTN-1', 'supplier': 'Supplier', 'promised_date': '2026-11-02',
                 'provenance': 'REAL', 'lines': [{'line_id': '1', 'material': 'Rebar', 'quantity': '10.25', 'unit': 't'}]}
    plan = client.post('/receiving/plans', headers=auth(), json=plan_body)
    assert plan.status_code == 201, plan.text
    payload = {'plan_id': plan.json()['id'], 'reference': 'TTN-1', 'observed_at': '2026-11-02T10:00:00+05:00',
               'time_source': 'device', 'provenance': 'REAL', 'lines': plan_body['lines'], 'condition': 'ok'}
    return client, auth, actors, site, plan.json(), payload


def record(setup, payload=None):
    client, auth, actors, site, plan, default = setup
    body = {'receipt_id': str(uuid4()), 'operation_id': str(uuid4()), 'payload': payload or default}
    result = client.post('/receiving/receipts', headers=auth('receiver'), json=body)
    assert result.status_code == 201, result.text
    return body, result.json()['receipt']


def attach(setup, packet):
    client, auth, *_ = setup
    response = client.post(f"/receiving/receipts/{packet['receipt_id']}/revisions/{packet['current_revision']}/attachments",
                           headers=auth('receiver'), files={'file': ('photo.png', PNG, 'image/png')})
    assert response.status_code == 201, response.text
    return response.json()


def confirm(setup, packet, role='receiver', decision='confirmed', reason=''):
    client, auth, *_ = setup
    body = {'decision_id': str(uuid4()), 'expected_revision': packet['current_revision'], 'decision': decision,
            'accepted': [{'line_id': x['line_id'], 'quantity': x['quantity']} for x in packet['current']['payload']['lines']],
            'reason': reason}
    result = client.post(f"/receiving/receipts/{packet['receipt_id']}/decisions", headers=auth(role), json=body)
    assert result.status_code == 200, result.text
    return body, result.json()


def test_capture_does_not_need_prediction_and_complete_confirmed_is_stricter(receiving, temp_db):
    body, packet = record(receiving)
    assert packet['current']['evidence_status'] == 'recorded'
    _, packet = confirm(receiving, packet)
    assert packet['current']['evidence_status'] == 'confirmed'
    assert not packet['current']['complete_confirmed']
    assert 'attachment' in packet['current']['missing']
    with temp_db['Session']() as db:
        assert db.query(temp_db['models'].PredictionLog).count() == 0


def test_complete_flow_and_manifest(receiving):
    client, auth, *_ = receiving
    _, packet = record(receiving)
    media = attach(receiving, packet)
    _, packet = confirm(receiving, packet)
    assert packet['current']['complete_confirmed']
    assert not packet['current']['location_available']
    assert packet['current']['payload']['lines'][0]['quantity'] == '10.25'
    exported = client.get(f"/receiving/receipts/{packet['receipt_id']}/export", headers=auth()).json()
    sha = exported.pop('manifest_sha256')
    assert sha == digest(exported)
    assert client.get(f"/receiving/attachments/{media['id']}", headers=auth()).content == PNG


def test_idempotency_and_changed_content_conflict(receiving):
    client, auth, *_ = receiving
    body, _ = record(receiving)
    assert client.post('/receiving/receipts', headers=auth('receiver'), json=body).json()['duplicate']
    body['payload']['condition'] = 'damaged'
    assert client.post('/receiving/receipts', headers=auth('receiver'), json=body).status_code == 409
    assert client.get('/receiving/receipts', headers=auth()).json()['total'] == 1


def test_concurrent_identical_receipt_retries(receiving):
    client, auth, *_, payload = receiving
    body = {'receipt_id': str(uuid4()), 'operation_id': str(uuid4()), 'payload': payload}
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: client.post('/receiving/receipts', headers=auth('receiver'), json=body), range(4)))
    assert [r.status_code for r in results] == [201] * 4
    assert sum(not r.json()['duplicate'] for r in results) == 1
    assert client.get('/receiving/receipts', headers=auth()).json()['total'] == 1


def test_correction_preserves_original_and_drops_confirmation(receiving):
    client, auth, *_ = receiving
    body, packet = record(receiving)
    attach(receiving, packet)
    decision, packet = confirm(receiving, packet)
    corrected = deepcopy(body['payload'])
    corrected['lines'][0]['quantity'] = '8.5'
    correction = {'operation_id': str(uuid4()), 'expected_revision': 1, 'reason': 'Recounted load', 'payload': corrected}
    url = f"/receiving/receipts/{packet['receipt_id']}/corrections"
    response = client.post(url, headers=auth('receiver'), json=correction)
    assert response.status_code == 200, response.text
    packet = response.json()['receipt']
    assert packet['current_revision'] == 2
    assert packet['revisions'][0]['superseded']
    assert packet['revisions'][0]['attestations'][0]['decision'] == 'confirmed'
    assert packet['current']['attestations'] == []
    assert not packet['current']['complete_confirmed']
    decision['decision_id'] = str(uuid4())
    assert client.post(f"/receiving/receipts/{packet['receipt_id']}/decisions", headers=auth('receiver'), json=decision).status_code == 409
    assert client.post(url, headers=auth('receiver'), json=correction).json()['duplicate']


def test_site_and_role_boundaries_include_media_and_exports(receiving):
    client, auth, actors, *_ = receiving
    body, packet = record(receiving)
    media = attach(receiving, packet)
    assert client.post('/receiving/receipts', headers=auth('viewer'), json=body).status_code == 403
    assert client.get('/receiving/receipts').status_code == 401
    other = client.post('/receiving/sites', json={'name': 'Other'}).json()
    outsider = client.post(f"/receiving/sites/{other['id']}/actors", json={'name': 'Outsider', 'role': 'coordinator'}).json()
    headers = {'Authorization': 'Bearer ' + outsider['credential']}
    for path in [f"/receipts/{packet['receipt_id']}", f"/receipts/{packet['receipt_id']}/export", f"/attachments/{media['id']}"]:
        assert client.get('/receiving' + path, headers=headers).status_code == 404
    assert client.get('/receiving/receipts', headers=headers).json()['receipts'] == []
    body['receipt_id'] = str(uuid4())
    body['operation_id'] = str(uuid4())
    assert client.post('/receiving/receipts', headers=headers, json=body).status_code == 404
    client.post(f"/receiving/actors/{actors['receiver']['id']}/revoke")
    assert client.get('/receiving/me', headers=auth('receiver')).status_code == 401


@pytest.mark.parametrize('change', [
    {'observed_at': '2026-11-02T10:00:00'},
    {'location': {'latitude': 200, 'longitude': 0, 'accuracy_m': 1}},
    {'lines': [{'line_id': '1', 'material': 'Rebar', 'quantity': '-1', 'unit': 't'}]},
    {'lines': [{'line_id': '1', 'material': 'Rebar', 'quantity': 'NaN', 'unit': 't'}]},
    {'unloading_at': '2026-11-01T00:00:00Z'},
])
def test_invalid_receipt_inputs(receiving, change):
    client, auth, *_, payload = receiving
    response = client.post('/receiving/receipts', headers=auth('receiver'), json={
        'receipt_id': str(uuid4()), 'operation_id': str(uuid4()), 'payload': {**payload, **change}})
    assert response.status_code == 422


def test_unmatched_partial_and_dispute_workflow(receiving):
    client, auth, *_, payload = receiving
    payload = {**payload, 'plan_id': None, 'reference': 'Unexpected'}
    _, packet = record(receiving, payload)
    _, packet = confirm(receiving, packet, decision='disputed', reason='Quantity uncertain')
    assert packet['current']['evidence_status'] == 'disputed'
    _, packet = confirm(receiving, packet, role='coordinator', reason='Recount verified')
    assert not packet['current']['complete_confirmed']
    assert 'delivery_match' in packet['current']['missing']


def test_media_retry_and_attestation_freeze(receiving):
    client, auth, *_ = receiving
    _, packet = record(receiving)
    media = attach(receiving, packet)
    assert attach(receiving, packet)['duplicate']
    confirm(receiving, packet)
    url = f"/receiving/receipts/{packet['receipt_id']}/revisions/1/attachments"
    assert client.post(url, headers=auth('receiver'), files={'file': ('new.png', PNG + b'new')}).status_code == 409
    assert client.post(url, headers=auth('receiver'), files={'file': ('bad.html', b'<script>bad</script>')}).status_code == 415


def test_simulated_receipts_cannot_be_promoted_or_shared(receiving):
    client, auth, *_, payload = receiving
    payload = {**payload, 'plan_id': None, 'provenance': 'SIM'}
    body, packet = record(receiving, payload)
    correction = {'operation_id': str(uuid4()), 'expected_revision': 1, 'reason': 'Try promotion',
                  'payload': {**payload, 'provenance': 'REAL'}}
    assert client.post(f"/receiving/receipts/{packet['receipt_id']}/corrections", headers=auth(), json=correction).status_code == 422
    attach(receiving, packet)
    _, packet = confirm(receiving, packet)
    assert not packet['current']['complete_confirmed']


def test_partner_scope_revocation_and_correction_invalidate_access(receiving):
    client, auth, *_ = receiving
    body, packet = record(receiving)
    attach(receiving, packet)
    confirm(receiving, packet)
    grant_body = {'receipt_id': packet['receipt_id'], 'expected_revision': 1, 'recipient': 'Design partner',
                  'purpose': 'Evaluate receipt', 'consent_reference': 'Written consent 001',
                  'expires_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}
    grant = client.post('/receiving/grants', headers=auth(), json=grant_body)
    assert grant.status_code == 201, grant.text
    key = {'X-Evidence-Key': grant.json()['credential']}
    shared = client.get('/receiving/shared-evidence', headers=key)
    assert shared.status_code == 200
    assert not {'location', 'recorded_by', 'attestations', 'note', 'attachments'} & shared.json().keys()
    assert client.get('/receiving/receipts', headers=key).status_code == 401
    correction = {'operation_id': str(uuid4()), 'expected_revision': 1, 'reason': 'Recheck', 'payload': body['payload']}
    assert client.post(f"/receiving/receipts/{packet['receipt_id']}/corrections", headers=auth(), json=correction).status_code == 200
    assert client.get('/receiving/shared-evidence', headers=key).status_code == 409
    client.post(f"/receiving/grants/{grant.json()['id']}/revoke", headers=auth())
    assert client.get('/receiving/shared-evidence', headers=key).status_code == 401


def test_reconciliation_and_independent_coverage_denominator(receiving):
    client, auth, actors, site, plan, payload = receiving
    _, packet = record(receiving)
    attach(receiving, packet)
    confirm(receiving, packet)
    doc = {'document_id': str(uuid4()), 'plan_id': plan['id'], 'kind': 'TTN', 'number': '123',
           'issuer': 'Supplier', 'issued_on': '2026-11-01', 'lines': payload['lines']}
    assert client.post('/receiving/documents', headers=auth(), json=doc).status_code == 201
    result = client.get(f"/receiving/documents/{doc['document_id']}/reconciliation", headers=auth()).json()
    assert result['lines'][0]['status'] == 'matched'
    params = {'start': '2026-11-02T00:00:00+05:00', 'end': '2026-11-03T00:00:00+05:00',
              'eligible_arrivals': 4, 'register_reference': 'Gate log 02 Nov'}
    metrics = client.get('/receiving/metrics', headers=auth(), params=params).json()
    assert metrics['recorded_coverage'] == metrics['confirmed_coverage'] == 0.25
    assert metrics['eligible_arrivals'] == 4


def test_pure_evidence_rules_known_answers():
    payload = {'plan_id': 'a', 'provenance': 'REAL', 'lines': [{'line_id': '1', 'quantity': '2.5'}]}
    summary = receipt_summary(payload, {'decision': 'confirmed', 'accepted': [{'line_id': '1', 'quantity': '2'}]}, 1)
    assert summary['partial_acceptance'] and summary['complete_confirmed']
    line = {'line_id': '1', 'quantity': '2', 'material': 'Steel', 'unit': 't'}
    assert reconciliation([line], [{**line, 'unit': 'kg'}])[0]['status'] == 'material_or_unit_mismatch'
    assert reconciliation([line], [line, {**line, 'unit': 'kg'}])[0]['status'] == 'ambiguous_receipt_lines'


def test_extensions_default_closed(receiving, monkeypatch):
    client, auth, *_ = receiving
    monkeypatch.delenv('SITEPULSE_ENABLE_RECONCILIATION')
    monkeypatch.delenv('SITEPULSE_ENABLE_PARTNER_SHARING')
    assert client.get('/receiving/documents', headers=auth()).status_code == 403
    assert client.get('/receiving/shared-evidence').status_code == 403


def test_concurrent_correction_retries_and_partial_review(receiving):
    client, auth, *_ = receiving
    _, packet = record(receiving)
    attach(receiving, packet)
    body = {'decision_id': str(uuid4()), 'expected_revision': 1, 'decision': 'confirmed',
            'accepted': [{'line_id': '1', 'quantity': '9'}]}
    response = client.post(f"/receiving/receipts/{packet['receipt_id']}/decisions", headers=auth('receiver'), json=body)
    assert response.json()['current']['needs_review']
    correction = {'operation_id': str(uuid4()), 'expected_revision': 1,
                  'reason': 'Synthetic correction test', 'payload': packet['current']['payload']}
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: client.post(f"/receiving/receipts/{packet['receipt_id']}/corrections",
                              headers=auth('receiver'), json=correction), range(4)))
    assert [r.status_code for r in results] == [200] * 4
    assert sum(not r.json()['duplicate'] for r in results) == 1


def test_optional_slots_overlap_roles_versions_and_notifications(receiving, monkeypatch):
    client, auth, actors, site, plan, payload = receiving
    assert client.get('/receiving/resources', headers=auth()).status_code == 403
    monkeypatch.setenv('SITEPULSE_ENABLE_OPERATIONS', '1')
    assert client.post('/receiving/resources', headers=auth('receiver'), json={'name':'Crane-1','kind':'crane'}).status_code == 403
    resource = client.post('/receiving/resources', headers=auth(), json={'name':'Crane-1','kind':'crane'}).json()
    assert len(client.get('/receiving/resources', headers=auth()).json()['resources']) == 1
    assert client.post('/receiving/resources', headers=auth(), json={'name':'Crane-1','kind':'crane'}).status_code == 409
    slots = []
    for _ in range(2):
        body = {'slot_id':str(uuid4()), 'resource_id':resource['id'], 'plan_id':plan['id'],
                'start_at':'2026-11-02T10:00:00+05:00', 'end_at':'2026-11-02T11:00:00+05:00'}
        response = client.post('/receiving/slots', headers=auth('receiver'), json=body)
        assert response.status_code == 201, response.text
        slots.append(response.json())
        assert client.post('/receiving/slots', headers=auth('receiver'), json=body).status_code == 201
        body['end_at'] = '2026-11-02T12:00:00+05:00'
        assert client.post('/receiving/slots', headers=auth('receiver'), json=body).status_code == 409
    assert len(client.get('/receiving/slots', headers=auth()).json()['slots']) == 2
    decision = {'expected_version':1, 'action':'approve', 'reason':'Confirmed by coordinator'}
    assert client.post(f"/receiving/slots/{slots[0]['id']}/decision", headers=auth('receiver'), json=decision).status_code == 403
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda slot: client.post(f"/receiving/slots/{slot['id']}/decision", headers=auth(), json=decision), slots))
    assert sorted(r.status_code for r in responses) == [200,409]
    approved = next(r.json() for r in responses if r.status_code == 200)
    assert client.post(f"/receiving/slots/{approved['id']}/decision", headers=auth(), json=decision).status_code == 409
    notices = client.get('/receiving/notifications', headers=auth()).json()
    assert notices['unread'] == 2  # retries never duplicate notifications
    notification_id = notices['notifications'][0]['id']
    assert client.post(f'/receiving/notifications/{notification_id}/read', headers=auth('receiver')).status_code == 404
    for _ in range(2):
        assert client.post(f'/receiving/notifications/{notification_id}/read', headers=auth()).status_code == 200
    assert client.get('/receiving/notifications', headers=auth()).json()['unread'] == 1
    assert client.get('/receiving/notifications', headers=auth('receiver')).json()['unread'] == 1
    assert client.get('/receiving/supplier-history', headers=auth()).json()['suppliers'] == []
    _, packet = record(receiving)
    attach(receiving, packet)
    confirm(receiving, packet)
    history = client.get('/receiving/supplier-history', headers=auth()).json()['suppliers']
    assert history[0]['receipts'] == history[0]['on_time'] == 1
    assert 0 < history[0]['ci_low'] < 1 and history[0]['ci_high'] == 1
    assert client.post(f"/receiving/slots/{approved['id']}/decision", headers=auth(),
                       json={'action':'cancel','expected_version':2,'reason':'No longer required'}).status_code == 200
    pending = next(s for s in slots if s['id'] != approved['id'])
    assert client.post(f"/receiving/slots/{pending['id']}/decision", headers=auth(), json=decision).status_code == 200


def test_plan_closure_audit_and_superseded_media_retry(receiving):
    client, auth, actors, site, plan, payload = receiving
    _, packet = record(receiving)
    media = attach(receiving, packet)
    assert packet['current']['plan']['supplier'] == 'Supplier'
    assert client.post(f"/receiving/plans/{plan['id']}/status", headers=auth('receiver'),
                       json={'status':'completed','reason':'Partial load reviewed'}).status_code == 403
    closed = client.post(f"/receiving/plans/{plan['id']}/status", headers=auth(),
                         json={'status':'completed','reason':'All partial loads reconciled'})
    assert closed.json()['status'] == 'completed'
    correction = {'operation_id':str(uuid4()),'expected_revision':1,'reason':'Observed quantity corrected',
                  'payload':packet['current']['payload']}
    assert client.post(f"/receiving/receipts/{packet['receipt_id']}/corrections", headers=auth('receiver'),json=correction).status_code == 200
    url = f"/receiving/receipts/{packet['receipt_id']}/revisions/1/attachments"
    duplicate = client.post(url, headers=auth('receiver'), files={'file':('synthetic.png',PNG,'image/png')})
    assert duplicate.json()['id'] == media['id'] and duplicate.json()['duplicate']
    assert client.post(url, headers=auth('receiver'), files={'file':('changed.png',PNG+b'changed','image/png')}).status_code == 409
    assert client.get('/receiving/audit', headers=auth('viewer')).status_code == 403
    events = client.get('/receiving/audit', headers=auth()).json()['events']
    assert any(e['action']=='plan.completed' and e['details']['reason']=='All partial loads reconciled' for e in events)


def test_concurrent_document_retry_is_one_record(receiving):
    client, auth, actors, site, plan, payload = receiving
    body = {'document_id':str(uuid4()), 'plan_id':plan['id'], 'kind':'TTN', 'number':'DOC-RETRY',
            'issuer':'Synthetic issuer','issued_on':'2026-11-02','lines':payload['lines']}
    with ThreadPoolExecutor(max_workers=3) as pool:
        responses=list(pool.map(lambda _: client.post('/receiving/documents', headers=auth(), json=body), range(3)))
    assert [r.status_code for r in responses] == [201]*3
    assert len(client.get('/receiving/documents',headers=auth()).json()['documents']) == 1
    body['number']='CHANGED'
    assert client.post('/receiving/documents',headers=auth(),json=body).status_code == 409
