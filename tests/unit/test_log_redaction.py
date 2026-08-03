"""Stage 11 — prove secrets are never emitted in redacted structured output."""

from __future__ import annotations

from decimal import Decimal

from pydantic import SecretStr

from app.core.config import Settings
from app.core.security import redact, redact_settings


def test_settings_redaction_hides_secrets():
    settings = Settings(
        exchange_api_key="AKIA_SUPER_SECRET_KEY_1234567890",
        exchange_api_secret="totally-secret-value-abcdefghijklmnop",
        live_approval_token="approval-token-zzzz-9999-secret-value",
    )
    safe = redact_settings(settings)
    dumped = str(safe)
    assert "AKIA_SUPER_SECRET_KEY_1234567890" not in dumped
    assert "totally-secret-value-abcdefghijklmnop" not in dumped
    assert "approval-token-zzzz-9999-secret-value" not in dumped
    assert safe["exchange_api_key"] == "***REDACTED***"
    assert safe["exchange_api_secret"] == "***REDACTED***"


def test_redact_masks_secret_keys_and_values():
    payload = {
        "api_key": "shhh-1234567890-abcdef",
        "password": "hunter2-hunter2-hunter2",
        "authorization": "Bearer abcdef0123456789abcdef",
        "nested": {"secret": SecretStr("nested-secret"), "ok": "public-value"},
        "amount": Decimal("100.00"),
    }
    safe = redact(payload)
    text = str(safe)
    assert "shhh-1234567890-abcdef" not in text
    assert "hunter2-hunter2-hunter2" not in text
    assert "nested-secret" not in text
    # Non-secret data is preserved.
    assert safe["nested"]["ok"] == "public-value"
    assert safe["amount"] == Decimal("100.00")


def test_secretstr_is_redacted():
    assert redact(SecretStr("my-secret")) == "***REDACTED***"
