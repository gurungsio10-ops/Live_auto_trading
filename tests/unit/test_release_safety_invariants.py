"""Release-branch safety invariants — paper-only, live fail-closed."""

from __future__ import annotations

from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.core.runtime_mode import RuntimeMode
from app.core.safety import SafetyGuard
from app.execution.live_gate import (
    LIVE_STARTUP_ACK_VALUE,
    LiveReadinessState,
    LiveTradingGate,
)


def test_default_mode_is_paper():
    get_settings.cache_clear()
    s = get_settings()
    assert s.trading_mode.lower() == "paper"
    assert s.live_trading_enabled is False
    assert s.runtime_mode == RuntimeMode.PAPER


def test_live_trading_gate_fail_closed_even_when_checklist_green():
    settings = Settings(
        trading_mode="live",
        live_trading_enabled=True,
        kill_switch_enabled=False,
        live_startup_ack=LIVE_STARTUP_ACK_VALUE,
        exchange_api_key=SecretStr("key-123456789012345678901234"),
        exchange_api_secret=SecretStr("secret-123456789012345678901234"),
        _env_file=None,
    )
    gate = LiveTradingGate(settings, LiveReadinessState(live_approval_valid=True))
    result = gate.evaluate()
    assert result.allowed is False
    assert (result.details or {}).get("live_execution_hard_blocked") is True


def test_safety_guard_paper_only_default():
    get_settings.cache_clear()
    SafetyGuard().assert_paper_only()
