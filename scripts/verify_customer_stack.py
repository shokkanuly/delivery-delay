"""Rehearse the actual customer containers with disposable SIM data and local TLS.

Requires Docker Compose v2 and httpx. Creates a unique project, loopback-only
ephemeral proxy ports and new volumes; never loads .env.customer. Removes only
its own containers/volumes. Does not install a CA in the machine's trust store.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import secrets
import ssl
import subprocess
import tempfile
import time
from uuid import uuid4

import httpx

from scripts.verify_receipt_bundle import verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', help='Use an already built application image')
    parser.add_argument('--report', default='test-results/receiving/customer-stack.json')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    project = 'sitepulse-rehearsal-' + uuid4().hex[:12]
    password, admin = secrets.token_hex(24), secrets.token_hex(32)
    env = dict(os.environ, POSTGRES_PASSWORD=password, SITEPULSE_ADMIN_KEY=admin,
               DATABASE_URL=f'postgresql+psycopg://sitepulse:{password}@db:5432/sitepulse',
               SITEPULSE_DOMAIN='localhost')
    report = {'passed': False, 'synthetic': True, 'checks': [],
              'notice': 'Disposable containers and local CA; not a customer host or public TLS verification.'}
    report_path = root / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    private_values = [password, admin]

    def run(command, *, content=None, check=True):
        result = subprocess.run(command, cwd=root, env=env, input=content,
                                capture_output=True, timeout=600)
        if check and result.returncode:
            detail = result.stderr.decode(errors='replace')[-5000:]
            for value in private_values:
                detail = detail.replace(value, '[redacted]')
            raise RuntimeError(f'Container command failed ({result.returncode}): {detail}')
        return result

    def passed(name):
        report['checks'].append(name)
        print('PASS: ' + name, flush=True)

    with tempfile.TemporaryDirectory(prefix=project) as directory:
        temporary = Path(directory)
        env_file = temporary / 'empty.env'
        env_file.touch(mode=0o600)
        base = ['docker', 'compose', '--project-name', project, '--env-file', str(env_file)]
        config = json.loads(run(base + ['-f', 'docker-compose.customer.yml', 'config', '--format', 'json']).stdout)
        # Fail if the customer topology gains a service or references shared volumes.
        assert set(config['services']) == {'db', 'api', 'proxy'}
        for section in ('volumes', 'networks'):
            for resource in config.get(section, {}).values():
                assert not resource.get('external')
                assert resource.get('name', '').startswith(project + '_')
        assert not config['services']['db'].get('ports')
        assert not config['services']['api'].get('ports')
        config['services']['proxy']['ports'] = [
            {'target': port, 'published': '0', 'host_ip': '127.0.0.1', 'protocol': 'tcp'}
            for port in (80, 443)]
        if args.image:
            config['services']['api']['image'] = args.image
        config_path = temporary / 'compose.json'
        with config_path.open('x', encoding='utf-8') as stream:
            os.chmod(config_path, 0o600)
            json.dump(config, stream)
        compose = base + ['-f', str(config_path)]
        try:
            run(compose + ['up', '-d', '--wait', '--wait-timeout', '180',
                           '--no-build' if args.image else '--build'])
            # Caddy uses its own local CA for localhost. Trust it only in this client.
            for attempt in range(60):
                copied = run(compose + ['cp', 'proxy:/data/caddy/pki/authorities/local/root.crt',
                                        str(temporary / 'root.crt')], check=False)
                if copied.returncode == 0:
                    break
                time.sleep(1)
            else:
                raise RuntimeError('Caddy did not create the local CA')
            tls = ssl.create_default_context(cafile=str(temporary / 'root.crt'))

            def client():
                port = run(compose + ['port', 'proxy', '443']).stdout.decode().strip().rsplit(':', 1)[1]
                return httpx.Client(base_url='https://localhost:' + port, verify=tls,
                                    trust_env=False, timeout=30)

            def request(http, method, path, expected=200, **kwargs):
                response = http.request(method, path, **kwargs)
                assert response.status_code == expected, f'{method} {path}: {response.status_code}, expected {expected}'
                return response

            with client() as http:
                for attempt in range(60):
                    try:
                        ready = request(http, 'GET', '/readyz').json()
                        assert ready['mode'] == 'customer'
                        break
                    except (httpx.TransportError, AssertionError):
                        if attempt == 59:
                            raise
                        time.sleep(1)
                shell = request(http, 'GET', '/receive')
                assert 'frame-ancestors' in shell.headers['content-security-policy']
                assert shell.headers['x-content-type-options'] == 'nosniff'
                assert 'max-age=' in shell.headers['strict-transport-security']
                request(http, 'GET', '/receive-sw.js')
                passed('Customer stack starts, migrates and serves receiving through verified local TLS')
                for path in ['/projects', '/health', '/docs', '/static/index.html',
                             '/static/samples/audit_report_synthetic.json']:
                    request(http, 'GET', path, 404)
                assert request(http, 'GET', '/receiving/me', 401).headers['cache-control'] == 'no-store'
                request(http, 'POST', '/receiving/sites', 401, json={'name': 'Denied'})
                operator = {'X-API-Key': admin}
                site = request(http, 'POST', '/receiving/sites', 201, headers=operator,
                               json={'name': 'SIM container rehearsal'}).json()
                actors = {}
                for role in ['coordinator', 'receiver', 'viewer']:
                    actor = request(http, 'POST', f"/receiving/sites/{site['id']}/actors", 201,
                                    headers=operator, json={'name': 'SIM ' + role, 'role': role}).json()
                    actors[role] = actor
                    private_values.append(actor['credential'])
                coordinator = {'Authorization': 'Bearer ' + actors['coordinator']['credential']}
                receiver = {'Authorization': 'Bearer ' + actors['receiver']['credential']}
                viewer = {'Authorization': 'Bearer ' + actors['viewer']['credential']}
                profile = request(http, 'GET', '/receiving/me', headers=coordinator).json()
                assert not any(profile['features'].values())
                assert request(http, 'GET', '/receiving/plans', headers=coordinator).json()['total'] == 0
                passed('Legacy routes are private, operator authentication works and extensions stay disabled')
                line = {'line_id': '1', 'material': 'SIM rebar', 'quantity': '2.5', 'unit': 't'}
                plan = request(http, 'POST', '/receiving/plans', 201, headers=coordinator, json={
                    'reference': 'SIM-CONTAINERS', 'supplier': 'SIM supplier', 'lines': [line],
                    'promised_date': datetime.now(timezone.utc).date().isoformat(), 'provenance': 'SIM'}).json()
                receipt_id = str(uuid4())
                body = {'receipt_id': receipt_id, 'operation_id': str(uuid4()), 'payload': {
                    'plan_id': plan['id'], 'reference': 'SIM-CONTAINERS', 'lines': [line],
                    'observed_at': datetime.now(timezone.utc).isoformat(), 'time_source': 'manual',
                    'provenance': 'SIM', 'condition': 'ok'}}
                request(http, 'POST', '/receiving/receipts', 403, headers=viewer, json=body)
                request(http, 'POST', '/receiving/receipts', 201, headers=receiver, json=body)
                assert request(http, 'POST', '/receiving/receipts', 201, headers=receiver,
                               json=body).json()['duplicate']
                photo = b'\x89PNG\r\n\x1a\nSIM-container-evidence'
                attachment = request(http, 'POST', f'/receiving/receipts/{receipt_id}/revisions/1/attachments',
                                     201, headers=receiver, files={'file': ('SIM.png', photo, 'image/png')}).json()
                packet = request(http, 'POST', f'/receiving/receipts/{receipt_id}/decisions',
                                 headers=receiver, json={'decision_id': str(uuid4()), 'expected_revision': 1,
                                 'decision': 'confirmed', 'accepted': [{'line_id': '1', 'quantity': '2.5'}]}).json()
                assert packet['current']['evidence_status'] == 'confirmed'
                assert not packet['current']['complete_confirmed']  # SIM never counts as field coverage.
                bundle = request(http, 'GET', f'/receiving/receipts/{receipt_id}/bundle', headers=viewer)
                assert verify(io.BytesIO(bundle.content))['attachments'] == 1
                passed('SIM plan, receipt, retry, private photo, confirmation and ZIP survive the proxy')

            run(compose + ['down'])  # Keep this rehearsal's volumes, then recreate every container.
            run(compose + ['up', '-d', '--wait', '--wait-timeout', '180', '--no-build'])
            with client() as http:
                # Proxy has no healthcheck; a successful TLS request is its readiness check.
                for attempt in range(60):
                    try:
                        request(http, 'GET', '/readyz')
                        break
                    except httpx.TransportError:
                        if attempt == 59:
                            raise
                        time.sleep(1)
                packet = request(http, 'GET', f'/receiving/receipts/{receipt_id}', headers=viewer).json()
                assert packet['current']['evidence_status'] == 'confirmed'
                assert not packet['current']['complete_confirmed']  # SIM never counts as field coverage.
                assert request(http, 'GET', f"/receiving/attachments/{attachment['id']}", headers=viewer).content == photo
                passed('Receipt, attachment, credentials and local CA persist after container recreation')
                request(http, 'POST', f"/receiving/actors/{actors['receiver']['id']}/revoke", headers=operator)
                request(http, 'GET', '/receiving/me', 401, headers=receiver)
                passed('Credential revocation takes effect through the deployed proxy')
            dump = run(compose + ['exec', '-T', 'db', 'pg_dump', '-U', 'sitepulse', '-d', 'sitepulse', '-Fc']).stdout
            run(compose + ['exec', '-T', 'db', 'createdb', '-U', 'sitepulse', 'rehearsal_restore'])
            run(compose + ['exec', '-T', 'db', 'pg_restore', '-U', 'sitepulse', '--no-owner', '--no-acl',
                           '--exit-on-error', '-d', 'rehearsal_restore'], content=dump)
            query = f"SELECT encode(content, 'hex') FROM receipt_attachments WHERE id='{attachment['id']}'"
            recovered = run(compose + ['exec', '-T', 'db', 'psql', '-U', 'sitepulse', '-d',
                                       'rehearsal_restore', '-At', '-v', 'ON_ERROR_STOP=1', '-c', query]).stdout
            assert bytes.fromhex(recovered.decode().strip()) == photo
            passed('Container-native dump/restore recovers exact attachment bytes into a separate database')
            report['passed'] = True
        finally:
            # Project is random and all volumes were verified to be project-owned above.
            cleanup = run(compose + ['down', '--volumes', '--remove-orphans'], check=False)
            report['cleanup_passed'] = cleanup.returncode == 0
            report['passed'] = report['passed'] and report['cleanup_passed']
            report_path.write_text(json.dumps(report, indent=2) + '\n')
            if not report['cleanup_passed']:
                raise RuntimeError('Disposable stack cleanup failed: ' + project)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
