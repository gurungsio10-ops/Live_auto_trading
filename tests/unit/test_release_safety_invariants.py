"""Release-branch safety invariants — paper-only, live fail-closed."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.runtime_mode import RuntimeMode
from app.core.safety import SafetyGuard
from app.execution.live_gate import LiveTradingGate


def test_default_mode_is_paper():
    get_settings.cache_clear()
    s = get_settings()
    assert s.trading_mode.lower() == "paper"
    assert s.enable_live_trading is False
    assert s.runtime_mode == RuntimeMode.PAPER


def test_live_trading_gate_fail_closed():
    gate = LiveTradingGate()
    result = gate.evaluate(
        enable_live_trading=True,
        trading_mode="live",
        kill_switch_enabled=False,
        credentials_present=True,
        reconciliation_healthy=True,
        market_data_healthy=True,
        risk_engine_healthy=True,
        live_ack_present=True,
    )
    assert result.allowed is False


def test_safety_guard_rejects_live_without_flag():
    guard = SafetyGuard()
    # Paper-only assertion must pass for default paper settings.
    guard.assert_paper_only()
