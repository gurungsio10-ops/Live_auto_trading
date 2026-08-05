"""Runtime mode + hard LIVE guard tests."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.core.errors import LiveTradingDisabledError
from app.core.runtime_mode import (
    RuntimeMode,
    derive_runtime_mode,
    normalize_runtime_mode,
)


def test_normalize_invalid_never_live():
    assert normalize_runtime_mode(None) == RuntimeMode.PAPER
    assert normalize_runtime_mode("") == RuntimeMode.PAPER
    assert normalize_runtime_mode("garbage") == RuntimeMode.PAPER
    assert normalize_runtime_mode("LIVE") == RuntimeMode.LIVE


def test_derive_from_exchange_env():
    assert (
        derive_runtime_mode(explicit=None, trading_mode="paper", exchange_env="testnet")
        == RuntimeMode.TESTNET
    )
    assert (
        derive_runtime_mode(explicit=None, trading_mode="paper", exchange_env="paper")
        == RuntimeMode.PAPER
    )
    assert (
        derive_runtime_mode(
            explicit="BACKTEST", trading_mode="paper", exchange_env="paper"
        )
        == RuntimeMode.BACKTEST
    )


def test_settings_default_runtime_paper():
    s = Settings(_env_file=None)
    assert s.trading_mode == "paper"
    assert s.runtime_mode == RuntimeMode.PAPER
    assert s.live_trading_enabled is False
    s.assert_startup_safe()


def test_invalid_trading_mode_falls_back_to_paper():
    s = Settings(trading_mode="banana", _env_file=None)  # type: ignore[arg-type]
    assert s.trading_mode == "paper"


def test_live_hard_blocked_even_with_all_gates():
    s = Settings(
        trading_mode="live",
        exchange_env="live",
        live_trading_enabled=True,
        exchange_api_key=SecretStr("k" * 24),
        exchange_api_secret=SecretStr("s" * 24),
        live_approval_token=SecretStr("approval-token-value-1234567890"),
        live_startup_ack="I_UNDERSTAND_LIVE_TRADING_RISKS",
        kill_switch_enabled=False,
        atlas_runtime_mode="LIVE",
        _env_file=None,
    )
    assert s.runtime_mode == RuntimeMode.LIVE
    with pytest.raises(LiveTradingDisabledError):
        s.assert_startup_safe()


def test_live_incomplete_gates_still_hard_blocked():
    s = Settings(
        trading_mode="live",
        exchange_env="live",
        live_trading_enabled=False,
        atlas_runtime_mode="LIVE",
        _env_file=None,
    )
    with pytest.raises(LiveTradingDisabledError):
        s.assert_startup_safe()


def test_enable_live_trading_alias():
    s = Settings(ENABLE_LIVE_TRADING=True, _env_file=None)  # type: ignore[call-arg]
    assert s.live_trading_enabled is True
