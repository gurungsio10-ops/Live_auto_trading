"""
Signed session tokens (HMAC-SHA256).

The wire format is intentionally identical to the frontend ``frontend/lib/auth.ts``
scheme (``base64url(json).base64url(hmac)``) so a token issued here can be verified
locally by the Next.js middleware, and vice versa. Both sides share
``ATLAS_AUTH_SECRET``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

DEFAULT_TTL_SECONDS = 60 * 60 * 8  # 8 hours
REMEMBER_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days


def _secret() -> bytes:
    return os.getenv("ATLAS_AUTH_SECRET", "atlas-dev-secret-change-me").encode()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(body: str) -> str:
    digest = hmac.new(_secret(), body.encode(), hashlib.sha256).digest()
    return _b64url(digest)


def create_session_token(username: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> str:
    payload = {"username": username, "exp": int(time.time()) + ttl_seconds}
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    return f"{body}.{_sign(body)}"


def verify_session_token(token: str | None) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    body, signature = token.split(".", 1)
    if not hmac.compare_digest(signature, _sign(body)):
        return None
    try:
        payload = json.loads(_b64url_decode(body))
    except (ValueError, json.JSONDecodeError):
        return None
    username = payload.get("username")
    exp = payload.get("exp")
    if not username or not isinstance(exp, int) or exp < int(time.time()):
        return None
    return {"username": username, "exp": exp}
