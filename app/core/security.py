"""Secret redaction helpers. Never log raw Settings secrets."""

from __future__ import annotations

import re
from typing import Any

from pydantic import SecretStr

from app.core.config import Settings

_SECRET_KEYS = {
    "exchange_api_key",
    "exchange_api_secret",
    "live_approval_token",
    "api_key",
    "api_secret",
    "secret",
    "password",
    "token",
    "authorization",
}

_REDACTED = "***REDACTED***"


def redact(value: Any) -> Any:
    """Recursively redact secret-like values for safe logging."""
    if isinstance(value, SecretStr):
        return _REDACTED
    if isinstance(value, Settings):
        return redact_settings(value)
    if isinstance(value, dict):
        return {
            str(k): (_REDACTED if _is_secret_key(str(k)) else redact(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return type(value)(redact(v) for v in value)
    if isinstance(value, str):
        return _redact_string(value)
    return value


def redact_settings(settings: Settings) -> dict[str, Any]:
    data = settings.model_dump()
    for key in list(data.keys()):
        if _is_secret_key(key):
            data[key] = _REDACTED
        else:
            data[key] = redact(data[key])
    return data


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in _SECRET_KEYS)


def _redact_string(value: str) -> str:
    # Mask long hex/base64-looking tokens that may be keys.
    if len(value) >= 24 and re.fullmatch(r"[A-Za-z0-9_\-/=+]+", value):
        return _REDACTED
    return value
