"""Phase 1: settings defaults and secret redaction."""

from __future__ import annotations

import os

from app.core.config import Settings, get_settings
from app.core.security import redact, redact_settings


def test_trading_mode_defaults_to_paper():
    get_settings.cache_clear()
    os.environ.pop("TRADING_MODE", None)
    settings = Settings(_env_file=None)
    assert settings.trading_mode == "paper"
    assert settings.live_trading_enabled is False
    assert settings.kill_switch_enabled is False


def test_redact_settings_hides_secrets():
    settings = Settings(
        exchange_api_key="supersecretexchangekey123456",
        exchange_api_secret="supersecretexchangesecret123456",
        live_approval_token="approval-token-value-1234567890",
        _env_file=None,
    )
    redacted = redact_settings(settings)
    assert redacted["exchange_api_key"] == "***REDACTED***"
    assert redacted["exchange_api_secret"] == "***REDACTED***"
    assert redacted["live_approval_token"] == "***REDACTED***"
    assert "supersecret" not in str(redacted)


def test_redact_dict():
    payload = {"api_key": "abcd", "symbol": "BTC/USDT", "nested": {"token": "xyz"}}
    assert redact(payload)["api_key"] == "***REDACTED***"
    assert redact(payload)["nested"]["token"] == "***REDACTED***"
    assert redact(payload)["symbol"] == "BTC/USDT"
