"""Execution backend factory tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.core.errors import ConfigurationError, LiveTradingDisabledError
from app.execution.exchange.testnet import ExchangeTestnetClient
from app.execution.factory import build_execution_backend
from app.execution.paper.engine import PaperTradingEngine


def test_factory_paper():
    settings = Settings(exchange_env="paper", _env_file=None)
    backend = build_execution_backend(settings)
    assert isinstance(backend, PaperTradingEngine)


def test_factory_live_raises():
    settings = Settings(exchange_env="live", trading_mode="paper", _env_file=None)
    with pytest.raises(LiveTradingDisabledError):
        build_execution_backend(settings)


def test_factory_testnet_requires_credentials():
    settings = Settings(
        exchange_env="testnet",
        exchange_api_key=None,
        exchange_api_secret=None,
        _env_file=None,
    )
    with pytest.raises(ConfigurationError):
        build_execution_backend(settings)


def test_factory_testnet_with_injected_api():
    settings = Settings(
        exchange_env="testnet",
        exchange_api_key=SecretStr("k" * 20),
        exchange_api_secret=SecretStr("s" * 20),
        _env_file=None,
    )
    api = MagicMock()
    backend = build_execution_backend(settings, api=api)
    assert isinstance(backend, ExchangeTestnetClient)
