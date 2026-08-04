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


def test_allowed_symbols_plain_env_value(tmp_path, monkeypatch):
    """Codespaces/.env.example use ALLOWED_SYMBOLS=BTC/USDT (not JSON)."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "TRADING_MODE=paper\nALLOWED_SYMBOLS=BTC/USDT\nENABLE_LIVE_TRADING=false\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("ALLOWED_SYMBOLS", raising=False)
    settings = Settings(_env_file=str(env_file))
    assert settings.supported_symbols == ("BTC/USDT",)


def test_allowed_symbols_json_list_still_works(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        'TRADING_MODE=paper\nALLOWED_SYMBOLS=["BTC/USDT","ETH/USDT"]\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("ALLOWED_SYMBOLS", raising=False)
    settings = Settings(_env_file=str(env_file))
    assert settings.supported_symbols == ("BTC/USDT", "ETH/USDT")


def test_env_example_parses():
    """Full committed .env.example must load without SettingsError."""
    settings = Settings(_env_file=".env.example")
    assert settings.trading_mode == "paper"
    assert "BTC/USDT" in settings.supported_symbols
    assert settings.live_trading_enabled is False
