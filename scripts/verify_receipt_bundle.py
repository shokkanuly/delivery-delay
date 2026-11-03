"""Verify a downloaded SitePulse ZIP without extracting files or executing archive content.

Standard-library only. This checks internal consistency, not authenticity or physical delivery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import PurePosixPath
import zipfile

MAX_BYTES = 102 * 1024 * 1024


def verify(path):
    with zipfile.ZipFile(path) as bundle:
        entries = bundle.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)) or len(names) > 1003:
            raise ValueError('Duplicate or excessive archive entries')
        if sum(entry.file_size for entry in entries) > MAX_BYTES:
            raise ValueError('Archive exceeds verification size limit')
        for name in names:
            parts = PurePosixPath(name)
            if parts.is_absolute() or '..' in parts.parts or '\\' in name or name != parts.as_posix():
                raise ValueError('Unsafe archive path')
        manifest = json.loads(bundle.read('manifest.json'))
        if manifest['format'] != 'sitepulse-receipt-bundle-v1':
            raise ValueError('Unsupported evidence bundle format')
        expected = [entry['path'] for entry in manifest['files']]
        if len(expected) != len(set(expected)) or set(names) != set(expected) | {'manifest.json'}:
            raise ValueError('Archive file list differs from manifest')
        for entry in manifest['files']:
            data = bundle.read(entry['path'])
            if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
                raise ValueError('File length or digest mismatch')
        packet = json.loads(bundle.read('receipt.json'))
        claimed = packet.pop('manifest_sha256')
        canonical = json.dumps(packet, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
        if hashlib.sha256(canonical).hexdigest() != claimed:
            raise ValueError('Receipt packet digest mismatch')
        if any(manifest[key] != packet[key] for key in ['receipt_id', 'site_id', 'current_revision']):
            raise ValueError('Receipt identity differs from bundle manifest')
        expected_files = {(rev['number'], f['id']): f for rev in packet['revisions'] for f in rev['attachments']}
        attachments = [entry for entry in manifest['files'] if entry['path'].startswith('attachments/')]
        actual_keys = [(entry['revision'], entry['attachment_id']) for entry in attachments]
        if len(actual_keys) != len(set(actual_keys)) or set(actual_keys) != set(expected_files):
            raise ValueError('Receipt attachment list differs from bundle manifest')
        for entry in attachments:
            expected_file = expected_files[(entry['revision'], entry['attachment_id'])]
            extension = {'image/jpeg': 'jpg', 'image/png': 'png', 'application/pdf': 'pdf'}[expected_file['content_type']]
            expected_path = f"attachments/revision-{entry['revision']}/{entry['attachment_id']}.{extension}"
            if entry['path'] != expected_path:
                raise ValueError('Attachment path differs from its revision identity')
            if entry['sha256'] != expected_file['sha256'] or entry['bytes'] != expected_file['size']:
                raise ValueError('Attachment metadata differs from receipt')
        return {'valid': True, 'revisions': len(packet['revisions']), 'attachments': len(attachments),
                'notice': 'Internal consistency verified; authenticity and physical delivery are not established.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive')
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.archive)))
    except (ValueError, KeyError, TypeError, zipfile.BadZipFile, OSError) as exc:
        raise SystemExit('Evidence verification failed: ' + str(exc))


if __name__ == '__main__':
    main()
