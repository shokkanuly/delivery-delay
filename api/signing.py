"""HMAC-SHA256 request signatures for machine-to-machine ingest (1C exports, gate scanners).

Ported unchanged from JanaМен (shokkanuly/posttech, app/integrations/signing.py).
Standard library primitives only. The signature binds method, path, time, a one-time
nonce and the body hash. The receiver stores the nonce, so a captured request cannot be
replayed. Keys come from SITEPULSE_INGEST_KEYS="key_id:secret,key_id2:secret2".
"""

import base64
import hashlib
import hmac
import re
import secrets
import time
from collections.abc import Mapping

MAX_SKEW_SECONDS = 300
NONCE = re.compile(r"[A-Za-z0-9_-]{16,64}")


class SignatureError(Exception):
    pass


def _signature(key: str, method: str, path: str, timestamp: str, nonce: str, body: bytes) -> str:
    message = "\n".join((method.upper(), path, timestamp, nonce, hashlib.sha256(body).hexdigest()))
    return base64.b64encode(
        hmac.new(key.encode(), message.encode(), hashlib.sha256).digest()
    ).decode()


def sign(
    key_id: str,
    key: str,
    method: str,
    path: str,
    body: bytes,
    now: float | None = None,
    *,
    nonce: str | None = None,
) -> dict[str, str]:
    timestamp = str(int(time.time() if now is None else now))
    nonce = nonce or secrets.token_hex(16)
    if not NONCE.fullmatch(nonce):
        raise ValueError("Invalid signing nonce")
    return {
        "X-Key-Id": key_id,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Signature": _signature(key, method, path, timestamp, nonce, body),
    }


def verify(
    headers: Mapping[str, str],
    keys: Mapping[str, str],
    method: str,
    path: str,
    body: bytes,
    now: float | None = None,
) -> str:
    """Return the nonce of a valid request; headers must be case-insensitive."""
    key = keys.get(headers.get("x-key-id", ""))
    timestamp = headers.get("x-timestamp", "")
    nonce = headers.get("x-nonce", "")
    if (
        not key
        or len(timestamp) > 20
        or not (timestamp.isascii() and timestamp.isdigit())
        or not NONCE.fullmatch(nonce)
    ):
        raise SignatureError
    if abs((time.time() if now is None else now) - int(timestamp)) > MAX_SKEW_SECONDS:
        raise SignatureError
    expected = _signature(key, method, path, timestamp, nonce, body)
    if not hmac.compare_digest(headers.get("x-signature", "").encode(), expected.encode()):
        raise SignatureError
    return nonce


def keys_from_env(raw: str | None) -> dict[str, str]:
    """Parse "id:secret,id2:secret2"; secrets shorter than 32 characters are ignored."""
    keys = {}
    for part in (raw or "").split(","):
        key_id, _, secret = part.strip().partition(":")
        if key_id and len(secret) >= 32:
            keys[key_id] = secret
    return keys
